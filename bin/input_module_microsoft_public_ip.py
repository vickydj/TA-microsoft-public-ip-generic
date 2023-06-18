# encoding = utf-8

import os
import sys
import time
import datetime
from lxml import html
import json
import csv
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

def validate_input(helper, definition):
    parameters = definition.parameters
    input_value = parameters.get('download_url_id', None)
    pass

def is_https_url(url):
    parsed_url = urlsplit(url)
    return parsed_url.scheme == 'https'
    
def get_download_link(helper,url):

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
    }
    
    try:
        response = helper.send_http_request(url, "GET", headers=headers, timeout=120, verify=False)
        response.raise_for_status()
        tree = html.fromstring(response.content)
        element = tree.xpath('//a[@data-bi-id="downloadretry"]')
        deep_link = element[0].attrib["href"]
        helper.log_debug("Check deeplink is https : {}".format(deep_link))
        
        if (is_https_url(deep_link)):
            return deep_link
        
    except Exception as e:
        helper.log_error("Exception on getting deep_link : {}".format(e))
        os._exit(1)


def index_events(helper,ew,item):

    index=helper.get_arg('index')
    input_name = helper.get_input_stanza_names()
    sourcetype = helper.get_sourcetype()
    source = "microsoft://{}".format(input_name).lower()
    host = 'localhost'
    # helper.log_debug(items)

    helper.log_debug("Indexing item {}".format(item))
    event=helper.new_event(
        item,
        time=datetime.datetime.now(),
        host=host,
        index=index,
        source=source,
        sourcetype=sourcetype,
        done=True,
        unbroken=True
    )
    ew.write_event(event)
    return

def index_json(helper,ew,response):
    index_counter=0
    helper.log_debug("JSON : {} ".format(response.text))
    obj = response.json()
    items = obj.get("values",[])
    for i in items:
        index_counter+=1
        text=json.dumps(i)
        index_events(helper,ew,text)
    helper.log_info("Indexed {} events into index={} sourcetype={} source={}".format(index_counter,helper.get_arg('index'),helper.get_sourcetype(),"Microsoft://{}".format(helper.get_input_stanza_names())))
    return

def index_csv(helper,ew,response):
    
    index_counter=0
    csv=response.text
    rows = csv.split('\n')
    fieldnames = rows[0].split(',')
    json_data = []
    for row in rows [1:(len(rows)-1)]:
        data = {}
        for i, value in enumerate(row.split(',')):
            data[fieldnames[i].strip()]=value.strip()
            index_counter+=1
            helper.log_debug("fieldname :\"{}\": \"value : \"{}\"".format(fieldnames[i].strip(),value.strip()))

        helper.log_debug("csv_json_converted_event: {}".format(data))
        index_events(helper,ew,"{}".format(json.dumps(data)))
    helper.log_info("Indexed {} events into index={} sourcetype={} source={}".format(index_counter,helper.get_arg('index'),helper.get_sourcetype(),"Microsoft://{}".format(helper.get_input_stanza_names())))
    return

def index_xml(helper, ew, response):
    
    index_counter = 0

    xml_tree = ET.fromstring(response.text)
    json_data = {}

    for region in xml_tree.findall('Region'):
        region_name = region.get('Name')
        ip_ranges = []
        index_counter += 1
        
        for ip_range in region.findall('IpRange'):
            subnet = ip_range.get('Subnet')
            ip_ranges.append(subnet)
        json_data[region_name] = ip_ranges

    helper.log_debug("xml_json_converted_event: {}".format(json.dumps(json_data)))
    index_events(helper,ew,"{}".format(json.dumps(json_data)))

    helper.log_info("Indexed {} events into index={} sourcetype={} source={}".format(
      index_counter, helper.get_arg('index'), helper.get_sourcetype(),
      "Microsoft://{}".format(helper.get_input_stanza_names())))
    return

def download_data(helper,deep_link):
    try:
        helper.log_info("Download file initiated : {}".format(deep_link))
        response = helper.send_http_request(deep_link, "GET", timeout=200,verify=False)
    
    except Exception as e:
        helper.log_error("Exception while downloading : {}".format(e))
        os._exit(1)
    return response
    
def collect_events(helper, ew):

    url="https://www.microsoft.com/en-{}/download/confirmation.aspx?id={}".format(helper.get_arg('url_region'),helper.get_arg('download_url_id'))

    deep_link=get_download_link(helper,url)
    response=download_data(helper,deep_link)
    try:
        file_format_local=helper.get_arg('file_format')

        if file_format_local.lower() == 'json':
            index_json(helper,ew,response)
        elif file_format_local.lower() == 'csv':
            index_csv(helper,ew,response)
        elif file_format_local.lower() == 'xml':
            index_xml(helper,ew,response)
        else:
            index_events(helper,ew,response.text)
            helper.log_info("Indexed raw events into index={} sourcetype={} source={}".format(helper.get_arg('index'),helper.get_sourcetype(),"Microsoft://{}".format(helper.get_input_stanza_names())))
                
    except Exception as e:
        helper.log_error("Exception while indexing : {}".format(e))
        os._exit(1)
