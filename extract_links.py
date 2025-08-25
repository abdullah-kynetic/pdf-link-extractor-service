from PyPDF2 import PdfReader
import sys
import re
import asyncio
import aiohttp
import json

def clean_agenda(pdf_path):
    reader = PdfReader(pdf_path)
    page_texts = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        page_texts.append((page_num, text))

    #combine all the pages into one string
    combined_text = " ".join([text for _, text in page_texts])
    combined_text = combined_text.replace("\n", " ")

    # Find the start position after "CALL TO ORDER"
    start_position = 0
    call_to_order_match = re.search(r'CALL TO ORDER', combined_text, re.IGNORECASE)
    if call_to_order_match:
        start_position = call_to_order_match.end()
    
    # Find the position of the second "ADJOURMENT"
    adjournment_count = 0
    stop_position = len(combined_text)
    
    # Search for ADJOURMENT only in the text after CALL TO ORDER
    text_after_call = combined_text[start_position:]
    for match in re.finditer(r'ADJOURNMENT', text_after_call, re.IGNORECASE):
        adjournment_count += 1
        if adjournment_count == 1:
            stop_position = start_position + match.end()
            break

    # Extract the text between CALL TO ORDER and second ADJOURMENT
    combined_text = combined_text[start_position:stop_position]
    # write combined text to a file
    with open("combined_text.txt", "w") as f:
        f.write(combined_text)
    # print(combined_text)
    
    # split all the agenda items based off the format 1. (number then a period)
    agenda_items = re.split(r'\b(?:[1-9]|[1-9]\d|100)\.\s+', combined_text)[1:]
    agenda_item_numbers = re.findall(r'\b([1-9]|[1-9]\d|100)\.\s+', combined_text)

    # set up a docket dictionary with key name agenda item number and value as the agenda item number
    docket_list = {
        "docket": []
    }
    for i in range(len(agenda_item_numbers)):
        # j = len(agenda_item_numbers) - i - 1
        docket_list["docket"].append(
            {
                "item_number": agenda_item_numbers[i],
                "raw_text": agenda_items[i]
            }
        )

    return docket_list

async def _get_pdf_title(url):
    """Fetch PDF metadata to extract title"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    # Try to get content-disposition header for filename
                    content_disposition = response.headers.get('Content-Disposition', '')
                    if 'filename=' in content_disposition:
                        filename = content_disposition.split('filename=')[1].strip('"').split('.')[0]
                        return filename
                    # If no filename in header, try to get from URL
                    if '.pdf' in url.lower():
                        filename = url.split('/')[-1]
                        return filename
    except Exception as e:
        
        return None

def _get_hyperlinks_from_pdf(pdf_path):
    """Get all hyperlinks from a PDF"""

    reader = PdfReader(pdf_path)

    # Collect all hyperlinks first
    all_links = []
    for page_num, page in enumerate(reader.pages, start=1):
        if "/Annots" not in page:
            continue
        for annot in page["/Annots"]:
            obj = annot.get_object()
            if "/A" in obj and "/URI" in obj["/A"]:
                uri = obj["/A"]["/URI"]
                if ".pdf" in uri:
                    all_links.append({
                        "page": page_num,
                        "link": uri,
                        "title": None
                    })
    return all_links

async def _get_pdf_title_from_source(all_links):
    # Get PDF titles asynchronously in batches
    # print("length of all_links", len(all_links))
    async def process_links():
        for i in range(0, len(all_links), 5):
            batch = all_links[i:i+5]
            # print("batch number", i, "of", len(all_links)//5)
            batch_titles = await asyncio.gather(*[_get_pdf_title(link["link"]) for link in batch])
            for j in range(len(batch)):
                all_links[i+j]["title"] = batch_titles[j]
        return all_links
    
    return await process_links()

def _match_attachments_to_docket_list(docket_list, all_links):
    unmatched_links = []
    for link in all_links:
        link_title = re.sub(r'^.*?([A-Z]+-\d+-\d+)', r'\1', link["title"]).lstrip().rstrip()
        # print("link title", link["title"], "or for ", link_title)

        match_found = False
        for docket in docket_list["docket"]:
            if link["title"] in docket["raw_text"] or link_title in docket["raw_text"]:
                # print("match found for link", link_title, "at docket", docket["item_number"])
                if "attachments" not in docket:
                    docket["attachments"] = []
                docket["attachments"].append(link)
                match_found = True
                break
        # note no match found for link
        if not match_found:
            unmatched_links.append(link)
            # print("match NOT found for link", link_title)
    
    docket_list["unmatched_links"] = unmatched_links
    # write docket list to a file
    with open("final_docket_list.json", "w") as f:
        json.dump(docket_list, f)
    return docket_list





if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    pdf_path = sys.argv[1]
    page_texts = clean_agenda(pdf_path)
   
    all_links = _get_hyperlinks_from_pdf(pdf_path)
    # print(all_links)
    all_links = asyncio.run(_get_pdf_title_from_source(all_links))
    
    with open("all_links.json", "w") as f:
        json.dump(all_links, f)
    # print(pdf_titles)
    docket_list = _match_attachments_to_docket_list(page_texts, all_links)
    
    # write docket list to a file
    with open("final_docket_list.json", "w") as f:
        json.dump(docket_list, f)
        
