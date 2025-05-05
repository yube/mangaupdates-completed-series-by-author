from bs4 import BeautifulSoup
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from urllib.parse import urljoin
import concurrent.futures
import re
from colorama import Fore, Style
import os
from tqdm import tqdm


MAX_WORKERS = 8
MAX_IMAGE_HEIGHT = 224
IMAGES_PER_ROW = 10
OUTPUT_FILENAME = "authorlist.png"

author_url = 'https://www.mangaupdates.com/author/ei3to2y/nagai-go'
username = 'usr'
password = 'pwd'

session = requests.Session()
login_url = 'https://www.mangaupdates.com/login.html'
payload = {'username': username, 'password': password, 'act': 'login'}
response = session.post(login_url, data=payload)
BASE_URL = 'https://www.mangaupdates.com'

def resize_image(img, max_height=MAX_IMAGE_HEIGHT):
    width, height = img.size
    if height > max_height:
        new_height = max_height
        aspect_ratio = width / height
        new_width = int(new_height * aspect_ratio)
        img = img.resize((new_width, new_height), Image.LANCZOS)
    return img

def parse_series_page(series_info):
    thread_session = requests.Session()
    series_name, series_link = series_info

    try:
        response = thread_session.get(series_link, timeout=15)
        series_soup = BeautifulSoup(response.text, 'html.parser')

        cat_divs = series_soup.find_all('div', {'class': 'info-box_sCat__QFEaH'})
        content_divs = series_soup.find_all('div', {'class': 'info-box_sContent__CTwJh'})

        for cat_div, content_div in zip(cat_divs, content_divs):
            cat_text = cat_div.get_text().strip()
            content_text = content_div.get_text().strip()
            if "Completely Scanlated?" in cat_text and content_text == "No":
                return None

        img_tags = series_soup.find_all('img', {'class': 'img-fluid'})
        if len(img_tags) >= 4:
            img_tag = img_tags[3]
            img_url = img_tag['src']

            if not img_url.startswith(('http:', 'https:')):
                img_url = urljoin(series_link, img_url)

            img_response = thread_session.get(img_url, timeout=15)
            img = Image.open(BytesIO(img_response.content)).convert("RGB")
            img = resize_image(img)
            return {'name': series_name, 'link': series_link, 'image': img}

    except Exception as e:
        print(f"Error processing {series_link}: {e}")
        return None

def break_text(text, max_length=19):
    words = text.split()
    lines, current_line = [], ""
    for word in words:
        if len(current_line) + len(word) + 1 > max_length:
            lines.append(current_line.strip())
            current_line = word
        else:
            current_line += " " + word
    lines.append(current_line.strip())
    return lines

def truncate_text(text, max_length=50):
    return text[:45] + "..." if len(text) > max_length else text

def create_montage(images, titles, author_name, images_per_row=IMAGES_PER_ROW, output_filename=OUTPUT_FILENAME):
    if not images:
        print("No images to create a montage.")
        return

    img_width, img_height = images[0].size
    text_height = 60
    title_height = 40
    new_img_height = img_height + text_height

    num_rows = (len(images) - 1) // images_per_row + 1
    montage_width = img_width * min(images_per_row, len(images))
    montage_height = new_img_height * num_rows + title_height

    montage = Image.new("RGB", (montage_width, montage_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(montage)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
        title_font = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    title_text = f"Series completely scanlated by {author_name}"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((montage_width - title_width) // 2, 10), title_text, font=title_font, fill=(0, 0, 0))

    for i, (img, title) in enumerate(zip(images, titles)):
        row, col = divmod(i, images_per_row)
        x_offset = col * img_width
        y_offset = row * new_img_height + title_height

        montage.paste(img, (x_offset, y_offset))
        truncated_title = truncate_text(title)
        lines = break_text(truncated_title)
        for j, line in enumerate(lines[:3]):  # Max 3 lines
            draw.text((x_offset, y_offset + img_height + j * 18), line, font=font, fill=(0, 0, 0))

    montage.save(output_filename)
    print(f"Montage saved as {output_filename}")

def modify_url(url):
    if 'orderby' in url:
        return re.sub(r'orderby=[^&]*', 'orderby=year', url)
    return url + ('&orderby=year' if '?' in url else '?orderby=year')

author_url = modify_url(author_url)
response = session.get(author_url)
soup = BeautifulSoup(response.text, 'html.parser')

divs = soup.find_all('div', {'class': 'ps-2'})
series_info_list = []

for div in divs[1:]:
    series_name = div.get_text().strip()
    link_tag = div.find('a')
    series_link = link_tag['href']
    series_info_list.append((series_name, series_link))

ended_series = []

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(parse_series_page, info): info for info in series_info_list}

    with tqdm(total=len(futures), desc="Fetching series pages", unit="series") as pbar:
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                print(f"{Fore.GREEN}{result['name']}{Style.RESET_ALL}: {result['link']}")
                ended_series.append(result)
            pbar.update(1)

images = [series['image'] for series in ended_series]
titles = [series['name'] for series in ended_series]
author_name = soup.title.get_text().split(' - ')[0]

create_montage(images, titles, author_name)
