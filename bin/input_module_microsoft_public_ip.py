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
import socket

def validate_input(helper, definition):
    parameters = definition.parameters
    input_value = parameters.get('download_url_id', None)
    pass

def is_https_url(url):
    parsed_url = urlsplit(url)
    return parsed_url.scheme == 'https'


def get_download_link(helper,url):

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    
    
    try:
        response = helper.send_http_request(url, "GET", headers=headers, timeout=120, verify=False)
        response.raise_for_status()
        tree = html.fromstring(response.content)

        script_content = tree.xpath('//script[contains(text(), "window.__DLCDetails__")]/text()')[0]
        helper.log_debug("Response content(script): {}".format(script_content))
        json_data = json.loads(script_content.split('window.__DLCDetails__ = ')[1].split(';</script>')[0])
        deep_link = json_data['dlcDetailsView']['downloadFile'][0]['url']
        if not deep_link:
            raise ValueError("Download link not found")
        helper.log_info("Download link: {}".format(deep_link))

       
        if (is_https_url(deep_link)):
            helper.log_info("Source :{} Destination : {} Status : Success".format("microsoft",socket.gethostname()))
            return deep_link
        
    except Exception as e:
        helper.log_error("Exception on getting deep_link : {}".format(e))
        helper.log_info("Source :{} Destination : {} Status : Failed".format("microsoft",socket.gethostname()))
        


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
    for item in items:
        index_counter+=1
        text=json.dumps(item)
        index_events(helper,ew,text)
    helper.log_info("Indexed {} events into index={} sourcetype={} source={}".format(index_counter,helper.get_arg('index'),helper.get_sourcetype(),"Microsoft://{}".format(helper.get_input_stanza_names())))
    return

def index_csv(helper,ew,response):
    
    index_counter=0
    csv=response.text
    rows = csv.split('\n')
    fieldnames = rows[0].split(',')

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
        response.raise_for_status()
        return response
    
    except Exception as e:
        helper.log_error("Exception while downloading : {}".format(e))
        sys._exit(1)
    

def check_internet(destination,helper):
    try:
        url=helper.get_global_setting("internet_check_url")
        if not url:
            url="https://www.google.com"
            
        helper.log_debug("selected url:{}".format(url))
        response = helper.send_http_request(url, "GET", timeout=5, verify=False)
        helper.log_debug("response status:{}".format(response.raise_for_status())) 
        return True
    
    except Exception as e: 
        helper.log_debug("Exception on internet check:{}".format(e))
        return False


def connectivity_check(destination,helper):
    if check_internet(destination,helper):
        helper.log_info("Source :{} Destination : {} Status : Success".format(socket.gethostname(),destination))
    else:
        helper.log_info("Source :{} Destination : {} Status : Failed".format(socket.gethostname(),destination))
    return 
    
def collect_events(helper, ew):
    
    connectivity_check("internet",helper)
    connectivity_check("microsoft",helper)
    
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
        sys._exit(1)
