#!/usr/bin/env python
# coding=utf-8
from __future__ import print_function
import json
import logging
import logging.config
import urllib2
import argparse
from urllib2 import URLError
import time

LOGGER_CONFIG = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'
        }
    },
    
    'formatters': {
        'simple': {
            'format': '[%(levelname)s] %(asctime)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },

    'loggers': {
        'console': {
            'level': 'INFO',
            'handlers': ['console']
        }
    }
}

    
logging.config.dictConfig(LOGGER_CONFIG)
logger = logging.getLogger('console')

IP_DETECT_URL = 'https://api.ipify.org?format=json'
UPDATE_URL = 'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}'


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config',
        dest='config',
        type=argparse.FileType('r'))
    return parser


def load_config():
    parser = create_parser()
    config = parser.parse_args()
    s = config.config.read()
    try:
        c = json.loads(s)
    except (TypeError, ValueError):
        print("Invalid JSON format")
        exit(1)
    return c


class IPUpdater(object):
    def __init__(self, config):
        self.config = config
        self.url = UPDATE_URL.format(
            zone_id=config['zone_id'], record_id=config['record_id'])
        self.last_public_ip = None

    def make_request(self):
        headers = {
            'X-Auth-Key': self.config['api_key'],
            'X-Auth-Email': self.config['email'],
        }
        request = urllib2.Request(self.url, headers=headers)
        return request

    def set_dns_record(self, ip):
        request = self.make_request()
        payload = {
            'type': 'A', 'content': ip, 'id': self.config['record_id'],
            'name': self.config['domain']
        }
        request.add_data(json.dumps(payload))
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'PUT'
        try:
            response = urllib2.urlopen(request, timeout=30)
        except URLError as err:
            logger.error("Error: %s", err)
            return False
        body = response.read()
        try:
            content = json.loads(body)
        except (TypeError, ValueError) as err:
            logger.error("%s", err)
            return False
        return content.get('success', False)

    def get_dns_record(self):
        config = self.config
        request = self.make_request()
        try:
            response = urllib2.urlopen(request, timeout=30)
        except URLError as err:
            logger.error("Error: %s", err)
            return None
        body = response.read()
        try:
            content = json.loads(body)
        except (TypeError, ValueError) as err:
            logger.error("Error: %s", err)
            return None
        result = content.get('result')
        if result:
            return result.get('content')
        else:
            logger.warning("DNS record returned without content")
            return None

    def get_local_ip(self):
        try:
            response = urllib2.urlopen(IP_DETECT_URL, timeout=30)
        except URLError as err:
            logger.error("Error: %s", err)
            return None
        body = response.read().decode('utf-8')
        try:
            content = json.loads(body)
        except (TypeError, ValueError) as err:
            logger.error("Error: %s", err)
            return None
        ip = content.get('ip')
        return ip

    def begin(self):
        while True:
            local_ip = self.get_local_ip()
            logger.info("============ start ip upadting ============")
            logger.info("Current local ip is: %s", local_ip)
            if not local_ip:
                logger.info("Fetch local ip failed, try again in 15s.")
                time.sleep(15)
                continue

            self.last_public_ip = local_ip
            record = self.get_dns_record()
            logger.info("Current record ip is: %s", record)
            if not record:
                logger.info("Fetch record ip failed, try again in 15s")
                time.sleep(15)
                continue
            elif record == local_ip:
                logger.info("DNS Record match local ip, try again in 30s.")
                time.sleep(30)
                continue

            for i in range(3):
                success = self.set_dns_record(local_ip)
                logger.info("Successfully updated record to %s", local_ip)
                if success:
                    break
            logger.info("************ dns record updated successfully ************")
            time.sleep(30)
            

def main():
    logger.info("Starting updaing...")
    config = load_config()
    updater = IPUpdater(config)
    updater.begin()


if __name__ == '__main__':
    main()
