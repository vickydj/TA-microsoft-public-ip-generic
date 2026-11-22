# encoding = utf-8

import csv
import io
import json
import socket
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from lxml import html

HEADERS = {
    # Microsoft's download pages return 403 for non-browser user agents.
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
}
DLC_MARKER = 'window.__DLCDetails__='


def validate_input(helper, definition):
    download_url_id = (definition.parameters.get('download_url_id') or '').strip()
    if not download_url_id.isdigit():
        raise ValueError(
            "Download URL ID must be the numeric id from "
            "https://www.microsoft.com/en-us/download/details.aspx?id=<id>")


def log_connection(helper, destination, ok):
    # Parsed by EXTRACT-connection_check (props.conf) for the Connection check dashboard.
    helper.log_info("Source : {} Destination : {} Status : {}".format(
        socket.gethostname(), destination, "Success" if ok else "Failure"))


def check_internet(helper):
    """Optional reachability check against the 'Internet check URL' add-on setting.

    Goes through send_http_request, so the configured proxy is used.
    An empty setting skips the check.
    """
    check_url = (helper.get_global_setting('internet_check_url') or '').strip()
    if not check_url:
        return True
    try:
        resp = helper.send_http_request(check_url, "GET", headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log_connection(helper, "internet", False)
        helper.log_error("Internet check to {} failed: {}".format(check_url, e))
        return False
    log_connection(helper, "internet", True)
    return True


def get_download_link(helper, url):
    """Return the https download URL from the Microsoft download details page, or None."""
    try:
        response = helper.send_http_request(url, "GET", headers=HEADERS, timeout=120)
        response.raise_for_status()
    except Exception as e:
        log_connection(helper, "microsoft", False)
        helper.log_error("Exception on getting deep_link : {}".format(e))
        return None
    log_connection(helper, "microsoft", True)

    try:
        tree = html.fromstring(response.content)
        scripts = tree.xpath('//script[contains(text(), "window.__DLCDetails__")]/text()')
        if not scripts:
            raise ValueError("window.__DLCDetails__ not found on page")
        details, _ = json.JSONDecoder().raw_decode(scripts[0].split(DLC_MARKER, 1)[1])
        files = details['dlcDetailsView']['downloadFile']
        deep_link = files[0]['url'] if files else None
    except Exception as e:
        helper.log_error("Exception on getting deep_link : could not parse {}: {}".format(url, e))
        return None

    if not deep_link:
        helper.log_error("Exception on getting deep_link : no download file listed on {}".format(url))
        return None
    if urlsplit(deep_link).scheme != 'https':
        helper.log_error("Exception on getting deep_link : refusing non-https link {}".format(deep_link))
        return None
    helper.log_info("Download link: {}".format(deep_link))
    return deep_link


def download_data(helper, deep_link):
    helper.log_info("Download file initiated : {}".format(deep_link))
    try:
        response = helper.send_http_request(deep_link, "GET", headers=HEADERS, timeout=200)
        response.raise_for_status()
    except Exception as e:
        helper.log_error("Exception while downloading {} : {}".format(deep_link, e))
        return None
    return response


def write_event(helper, ew, data, source):
    ew.write_event(helper.new_event(
        data,
        time="%.3f" % time.time(),
        index=helper.get_arg('index'),
        source=source,
        sourcetype=helper.get_sourcetype(),
        done=True,
        unbroken=True))


def iter_json(response):
    for item in response.json().get("values", []):
        yield json.dumps(item)


def iter_csv(response):
    reader = csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')))
    for row in reader:
        yield json.dumps({(k or '').strip(): (v or '').strip() for k, v in row.items()})


def iter_xml(response):
    # Single event {region_name: [subnets]}, e.g. PublicIPs_<date>.xml (id=41653)
    root = ET.fromstring(response.content)
    yield json.dumps({
        region.get('Name'): [r.get('Subnet') for r in region.findall('IpRange')]
        for region in root.findall('Region')
    })


def iter_raw(response):
    yield response.text


PARSERS = {'json': iter_json, 'csv': iter_csv, 'xml': iter_xml, 'raw': iter_raw}


def collect_events(helper, ew):
    input_name = helper.get_input_stanza_names()
    source = "microsoft://{}".format(input_name).lower()
    url = "https://www.microsoft.com/en-{}/download/details.aspx?id={}".format(
        helper.get_arg('url_region') or 'us', (helper.get_arg('download_url_id') or '').strip())
    helper.log_info("URL : {}".format(url))

    if not check_internet(helper):
        return

    deep_link = get_download_link(helper, url)
    if not deep_link:
        return
    response = download_data(helper, deep_link)
    if response is None:
        return

    file_format = (helper.get_arg('file_format') or 'raw').lower()
    parser = PARSERS.get(file_format, iter_raw)
    count = 0
    try:
        for data in parser(response):
            write_event(helper, ew, data, source)
            count += 1
    except Exception as e:
        helper.log_error("Error processing {} data from {} after {} events: {}".format(
            file_format, deep_link, count, e))
        return

    helper.log_info("Indexed {} events into index={} sourcetype={} source={}".format(
        count, helper.get_arg('index'), helper.get_sourcetype(), source))
