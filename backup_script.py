import json
import os
import asyncio
from pyppeteer import launch
from datetime import datetime, timedelta, UTC, timezone
import shutil


def backup_bookmarks(source_path, destination_path):
    shutil.copy2(source_path, destination_path)


async def url_to_pdf(url, output_filename):
    browser = await launch()
    page = await browser.newPage()
    await page.goto(url)
    await page.pdf({'path': output_filename})
    await browser.close()

def chrome_timestamp_to_datetime(chrome_timestamp):
    # Chrome's timestamp is in microseconds since January 1, 1601
    microseconds_since_1601 = int(chrome_timestamp)
    # Unix timestamp is in seconds since January 1, 1970
    # Calculate offset in seconds from 1601 to 1970
    seconds_since_1601_to_1970 = (369 * 365 + 89) * 24 * 3600
    # Convert the difference to microseconds
    microseconds_since_1601_to_1970 = seconds_since_1601_to_1970 * 1_000_000
    # Convert Chrome timestamp to Unix timestamp in seconds
    unix_timestamp_seconds = (microseconds_since_1601 - microseconds_since_1601_to_1970) / 1_000_000
    # Convert Unix timestamp to datetime, setting timezone to UTC
    return datetime.fromtimestamp(unix_timestamp_seconds, tz=timezone.utc)



def load_chrome_bookmarks(bookmarks_path):
    with open(bookmarks_path, 'r', encoding='utf-8') as file:
        bookmarks = json.load(file)
    return bookmarks


def get_last_run(output_directory):
    last_run_path = os.path.join(output_directory, 'last_run.txt')
    try:
        with open(last_run_path, 'r') as file:
            last_run_str = file.read().strip()
            # Parse as UTC datetime and remove timezone info to make it offset-naive
            return datetime.strptime(last_run_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    except FileNotFoundError:
        # Return the earliest possible datetime, offset-naive
        return datetime.min.replace(tzinfo=timezone.utc)


def update_last_run(output_directory):
    last_run_path = os.path.join(output_directory, 'last_run.txt')
    with open(last_run_path, 'w') as file:
        file.write(datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S'))


async def process_bookmarks(bookmarks, output_directory, last_run):
    one_week_ago = datetime.now(UTC) - timedelta(days=7)
    print(one_week_ago)
    for bookmark in bookmarks:
        if bookmark['type'] == 'folder':
            await process_bookmarks(bookmark['children'], output_directory, last_run)
        elif bookmark['type'] == 'url':
            bookmark_date = chrome_timestamp_to_datetime(bookmark['date_added'])
            print(bookmark_date)
            if bookmark_date >= one_week_ago and bookmark_date > last_run:
                filename = f"{bookmark['name']}.pdf".replace('/', '-')
                output_filename = os.path.join(output_directory, filename)
                await url_to_pdf(bookmark['url'], output_filename)
                print(f"Saved {bookmark['name']} as PDF. filename: {output_filename}")


def generate_html(bookmarks, output_html_path):
    # Collect all bookmarks in a flat list with their details
    bookmark_list = []
    def collect_bookmarks(bookmarks):
        for bookmark in bookmarks:
            if bookmark['type'] == 'folder':
                collect_bookmarks(bookmark['children'])
            elif bookmark['type'] == 'url':
                bookmark_date = chrome_timestamp_to_datetime(bookmark['date_added'])
                bookmark_list.append({
                    'name': bookmark['name'],
                    'url': bookmark['url'],
                    'date': bookmark_date
                })

    collect_bookmarks(bookmarks)

    # Sort the list by date descending
    sorted_bookmarks = sorted(bookmark_list, key=lambda x: x['date'], reverse=True)

    # Create HTML content
    # Create HTML content
    html_content = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">' \
                   '<meta name="viewport" content="width=device-width, initial-scale=1.0">' \
                   '<style>' \
                   'li { margin-bottom: 10px; }' \
                   '</style>' \
                   '<title>Bookmarks</title></head><body><h1>Bookmarks</h1><ul>'

    for bookmark in sorted_bookmarks:
        # Format the date to DD-MM-YYYY
        formatted_date = bookmark['date'].strftime('%m-%d-%Y')
        html_content += f'<li><a href="{bookmark["url"]}">{bookmark["name"]}</a>    {formatted_date}</li>'

    html_content += '</ul></body></html>'

    # Save the HTML file
    with open(output_html_path, 'w', encoding='utf-8') as file:
        file.write(html_content)
    print(f"HTML file saved: {output_html_path}")


if __name__ == '__main__':
    # Adjust the path according to your operating system and username
    path_to_bookmarks = os.path.expanduser('~') + '/Library/Application Support/Google/Chrome/Default/Bookmarks'
    bookmarks_data = load_chrome_bookmarks(path_to_bookmarks)
    output_directory = os.path.expanduser('~') + "/Documents/bookmarkstorage2/"
    os.makedirs(output_directory, exist_ok=True)

    # Backup the bookmarks file
    backup_filename = os.path.join(output_directory, "BookmarksBackup.json")
    backup_bookmarks(path_to_bookmarks, backup_filename)

    last_run = get_last_run(output_directory)

    # Creating a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    all_bookmarks = []
    for key in ['bookmark_bar', 'other', 'synced']:  # Add here any other root keys if necessary
        if key in bookmarks_data['roots']:
            all_bookmarks.extend(bookmarks_data['roots'][key]['children'])
            # loop.run_until_complete(process_bookmarks(bookmarks_data['roots'][key]['children'], output_directory))
            loop.run_until_complete(
                process_bookmarks(bookmarks_data['roots'][key]['children'], output_directory, last_run))
    loop.close()
    # Generate HTML file
    html_output_path = os.path.join(output_directory, "Bookmarks.html")
    generate_html(all_bookmarks, html_output_path)
    update_last_run(output_directory)
