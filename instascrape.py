import argparse
import asyncio
import csv
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import coloredlogs
import enlighten
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def login(args, browser, account, password, logger):
    """Login to the Instagram account."""
    logger.info(f"Logging in with {account}'s Instagram account ...")

    browser.get("https://www.instagram.com/accounts/login/")
    time.sleep(1)  # find element won't work if this is removed

    login = browser.find_element_by_xpath("//input[@name='username']")
    passwd = browser.find_element_by_xpath("//input[@name='password']")
    login.send_keys(account)
    passwd.send_keys(password)
    login.submit()
    time.sleep(2)

    browser.get(f"https://www.instagram.com/{account}/saved/?hl=en")

    if not "Page introuvable" in browser.page_source:
        return True
    else:
        logger.setLevel(logging.ERROR)
        logger.error("Could not log into " + account +
                     "'s Instagram account. ")
        return False


def parse_args():
    """Parse console arguments."""
    parser = argparse.ArgumentParser(
        description=
        "Instagram location and tag gathering tool.",
    )

    parser.add_argument(
        "--url",
        dest="url",
        help="Instagram location url to start with"
    )

    parser.add_argument(
        "-t",
        "--tags",
        dest="tags",
        nargs='*',
        default=[],
        help="Filter tag"
    )

    parser.add_argument(
        "-l",
        "--login",
        dest="login",
        help=
        "Instagram profile to connect to, in order to access the instagram posts of the target account",
    )

    parser.add_argument(
        "-p",
        "--password",
        dest="password",
        help="Password of the Instagram profile to connect to",
    )

    parser.add_argument(
        "--max-scrolls",
        dest="max_scrolls",
        type=int,
        default=1000000,
        help="Maximum number of scrolls to perform on the page"
    )

    parser.add_argument(
        "-v",
        "--visual",
        action='store_true',
        help="Spawns Chromium GUI, otherwise Chromium is headless",
    )

    parser.add_argument(
        "-o",
        "--output",
        dest='output',
        help="Output file",
    )

    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Tells browser not to load images, for faster surfing"
    )

    parser.add_argument(
        '--scroll-wait-time',
        type=float,
        default=1,
        help='Waiting time between scrolls'
    )

    return parser.parse_args()


def init_logger():
    """Initialize the logger of the program. """
    logger = logging.getLogger(__name__)
    coloredlogs.install(level='INFO',
                        logger=logger,
                        fmt='[+] %(asctime)s - %(message)s',
                        stream=sys.stdout)

    return logger


def selenium_to_requests_session(browser):
    """Transfer selenium's session cookies to requests session."""
    selenium_cookies = browser.get_cookies()

    requests_session = requests.Session()

    for cookie in selenium_cookies:
        requests_session.cookies.set(cookie.get("name"), cookie.get("value"))

    return requests_session


def launch_browser(options):
    """Launch the ChromeDriver with specific options."""
    driver = webdriver.Chrome(options=options)
    return driver
    # return webdriver.Chrome("/usr/bin/chromedriver", chrome_options=options)


def scrolls(publications):
    """Number of scrolls required to catch all the pictures links."""
    return (int(publications)) // 11


def fetch_urls(browser, max_scrolls, scroll_wait_time, logger):
    """Catch all the pictures links of the Instagram profile."""
    links = []
    links.extend(re.findall("/p/([^/]+)/", browser.page_source))

    logger.info(
        "Scrolling the Instagram, scraping pictures URLs ... ")

    pbar = enlighten.Counter(total=max_scrolls, desc='Scrolling', unit='scrolls')

    try:
        prev_link_batch = None
        scroll_count = 0
        while scroll_count < max_scrolls:
            page_source = browser.page_source

            # check if browser has Loading icon, i.e. there is still new images to load
            if not "Loading..." in page_source:
                logger.info(
                    f"`Loading...` string not found, I suppose that the we reached the end of page. Stopping scrolling. (scroll count: {scroll_count})")
                break

            # scroll
            browser.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            link_batch = re.findall("/p/([^/]+)/", page_source)
            if link_batch == prev_link_batch:
                logger.warning("Ineffective scroll")
            else:
                links.extend(link_batch)
                scroll_count += 1
                pbar.update()
            prev_link_batch = link_batch

            # sleep between scrolls
            time.sleep(scroll_wait_time)
        if max_scrolls == scroll_count:
            logger.info(f"Reached max_scrolls. Stop scrolling. (scroll count: {max_scrolls})")
    except KeyboardInterrupt as e:
        logger.warning('KeyboardInterrupt. Stopping scrolling and will continue with the rest.')
    except Exception as e:
        logger.warning('Error occured while scrolling: %s', e)
        logger.warning("But we will continue with what we have scraped so far ;)")
    logger.info("Pictures links collected")
    return list(set(links))  # remove duplicates


def parse_tags(content):
    # shared_data_str = re.search("window\._sharedData = {(.*)};", content).group(0)
    texts = '\n'.join(re.findall("\"text\":\"([^\"]*)\"", content))
    tags = re.findall(r"(?:#)([A-Za-z0-9_](?:(?:[A-Za-z0-9_]|(?:\.(?!\.))){0,28}(?:[A-Za-z0-9_]))?)", texts)
    return tags


def fetch_tags(links, logger, filter_tags, requests_session=None):
    link2tags = dict()
    max_wrk = len(links)

    logger.info("Scraping and filtering tags for each picture: " +
                str(len(links)) + " links processed asynchronously")

    executor = ThreadPoolExecutor(
        max_workers=max_wrk
    )  # didnt find any information about Instagram / Facebook Usage Policy ... people on stackoverflow say there's no limit if you're not using any API so ... ¯\_(ツ)_/¯
    loop = asyncio.get_event_loop()

    async def make_requests(requests_session):
        if requests_session:
            session = requests_session
        else:
            session = requests.Session()
        futures = [
            loop.run_in_executor(executor, session.get,
                                 "https://www.instagram.com/p/" + url)
            for url in links
        ]
        await asyncio.wait(futures)
        return futures

    futures = loop.run_until_complete(make_requests(requests_session))
    number_locs = len(futures)
    assert number_locs == len(links), (number_locs, len(links))

    for link, future in zip(links, futures):
        content = future.result().text
        try:
            tags = parse_tags(content)
            # lower tags
            tags = [t.lower() for t in tags]
            # skip posts which don't intersect with filter tags
            if filter_tags and not set(tags).intersection(filter_tags):
                continue
        except Exception:
            logger.info(f"Couldn't parse tags for {link}")
            tags = []
        link2tags[link] = tags

    logger.info("Tags data scrapped successfully")
    return link2tags


def export_data(link2tags, output, logger):
    logger.info("Exporting data ...")
    with open(output, 'w') as f:
        writer = csv.writer(f)
        # write header
        max_tags = 30
        writer.writerow(["full_url", "link"] + ["tag" + str(i) for i in range(1, max_tags + 1)])
        for link, tags in link2tags.items():
            tags = tags[:max_tags]
            full_url = "https://www.instagram.com/p/" + link
            writer.writerow((full_url, link, *tags))

    logger.info("Wrote data successfully to " + output)


def main():
    args = parse_args()

    logger = init_logger()
    logger.info(f"url: {args.url}")

    logger.info(f"filter tags: {' | '.join(args.tags)}")
    if any(('#' in t for t in args.tags)):
        logger.error('Please specify filter tags without `#`')
        exit()
    if not args.tags:
        logger.info("No filter tags specified. Posts will not be filtered by tags.")

    # lowercase tags
    args.tags = [t.lower() for t in args.tags]

    browser_options = Options()
    if not args.visual:
        browser_options.add_argument("--headless")
    if args.no_images or not args.visual:
        prefs = {"profile.managed_default_content_settings.images": 2}
        browser_options.add_experimental_option("prefs", prefs)
    browser = launch_browser(browser_options)

    logged_in = False
    if args.login is not None and args.password is not None:
        logged_in = login(args, browser, args.login, args.password, logger)
        if not logged_in:
            exit()

    browser.get(url=args.url + '?hl=en')

    links = fetch_urls(browser, args.max_scrolls, args.scroll_wait_time, logger)

    requests_session = None
    if logged_in and browser:
        try:
            requests_session = selenium_to_requests_session(browser)
            browser.quit()
        except Exception as e:
            logger.warning('Error when requesting session from browser: %s', e)
            logger.warning('We will continue without login session')

    link2tags = fetch_tags(links, logger, filter_tags=args.tags, requests_session=requests_session)
    export_data(link2tags, args.output, logger)


if __name__ == "__main__":
    main()
