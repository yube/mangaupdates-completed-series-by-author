from bs4 import BeautifulSoup
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from urllib.parse import urljoin
import time

url = 'https://www.mangaupdates.com/author/ei3to2y/nagai-go' # replace with the author page you want
username = 'your username here'
password = 'your password here'


session = requests.Session()

# Login URL
login_url = 'https://www.mangaupdates.com/login.html'

# Prepare the payload with your username and password
payload = {'username': username, 'password': password, 'act': 'login'}

# Perform login
response = session.post(login_url, data=payload)

def resize_image(img, max_height=224):
    width, height = img.size
    if height > max_height:
        new_height = max_height
        aspect_ratio = width / height
        new_width = int(new_height * aspect_ratio)
        img = img.resize((new_width, new_height), Image.ANTIALIAS)
    return img


def parse_series_page(url):
    response = session.get(url)
    series_soup = BeautifulSoup(response.text, 'html.parser')

    for type_tag in series_soup.find_all('div', {'class': 'sContent'}):
        type_text = type_tag.get_text().strip()

    # Check for "Completely Scanlated? No"
    for cat_div, content_div in zip(series_soup.find_all('div', {'class': 'sCat'}),
                                    series_soup.find_all('div', {'class': 'sContent'})):
        cat_text = cat_div.get_text().strip()
        content_text = content_div.get_text().strip()
        if "Completely Scanlated?" in cat_text and content_text == "No":
            return None  # Return None to indicate this should be skipped

    img_tags = series_soup.find_all('img', {'class': 'img-fluid'})
    if len(img_tags) >= 4:
        img_tag = img_tags[3]
        img_url = img_tag['src']

        if not img_url.startswith(('http:', 'https:')):
            img_url = urljoin(url, img_url)

        try:
            img_response = requests.get(img_url)
            img = Image.open(BytesIO(img_response.content))
            return img
        except requests.exceptions.MissingSchema:
            print("Invalid URL for image:", img_url)
            return None
    else:
        print(f"skipped  {url}")
    return None


def break_text(text, max_length=19):
    if len(text) <= max_length:
        return [text]

    lines = []
    current_line = ""

    for word in text.split(" "):
        if len(current_line) + len(word) + 1 > max_length:
            lines.append(current_line)
            current_line = ""

        current_line += (word + " ")

    lines.append(current_line)
    return lines


def truncate_text(text, max_length=50):
    if len(text) > max_length:
        return text[:45] + "..."
    return text


def create_montage(images, titles, author_name, images_per_row=10):
    images = [img for img in images if img is not None]

    if len(images) == 0:
        print("No images to create a montage.")
        return

    img_width, img_height = images[0].size
    text_height = 60
    title_height = 40  # Height for the title text
    new_img_height = img_height + text_height

    num_rows = (len(images) - 1) // images_per_row + 1
    montage_width = img_width * min(images_per_row, len(images))
    montage_height = new_img_height * num_rows + title_height  # Adding height for title

    montage = Image.new(mode="RGB", size=(montage_width, montage_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(montage)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
        title_font = ImageFont.truetype("arial.ttf", 24)  # Font for title
    except IOError:
        print("Arial font not found, using default.")
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    # Draw title
    title_text = f"Series completed by {author_name}"
    title_width, title_height_actual = draw.textsize(title_text, font=title_font)
    title_position = ((montage_width - title_width) // 2, 10)  # X-center the text
    draw.text(title_position, title_text, font=title_font, fill=(0, 0, 0))

    for i, (img, title) in enumerate(zip(images, titles)):
        row = i // images_per_row
        col = i % images_per_row
        x_offset = col * img_width
        y_offset = row * new_img_height + title_height  # Y-offset adjusted for title height

        montage.paste(img, (x_offset, y_offset))

        truncated_title = truncate_text(title)
        lines = break_text(truncated_title)
        for j, line in enumerate(lines):
            draw.text((x_offset, y_offset + img_height + j * 20), line.strip(), font=font, fill=(0, 0, 0))

    # montage.show()
    montage.save("authorlist.png")

def modify_url(url):
    import re
    # Check if 'orderby' is present in the URL
    if 'orderby' in url:
        # Replace the existing 'orderby' parameter with 'year'
        url = re.sub(r'orderby=[^&]*', 'orderby=year', url)
    else:
        # If 'orderby' is not present, add it at the end
        if '?' in url:
            url += '&orderby=year'
        else:
            url += '?orderby=year'
    return url


url = modify_url(url)
ended_series = []

response = session.get(url)
soup = BeautifulSoup(response.text, 'html.parser')
divs = soup.find_all('div', {'class': 'pl-2'})
for i,div in enumerate (divs[1:], start =1):
    if i % 3 == 0:
        time.sleep(3)
    series_name = div.get_text().strip()
    link_tag = div.find('a')
    series_link = link_tag['href']
    series_image = parse_series_page(series_link)
    if series_image is not None:
        print(f"{series_name}: {series_link}")
        ended_series.append({
            'name': series_name,
            'link': series_link,
            'image': series_image
        })


images = [series.get('image', None) for series in ended_series]
titles = [series.get('name', '') for series in ended_series]
resized_images = [resize_image(img) for img in images]
author_name = soup.title.get_text()
split = author_name.split(' - ')
author_name = split[0]

create_montage(resized_images, titles, author_name)
