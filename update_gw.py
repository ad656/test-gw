import os
import time
import datetime
import requests
import sys
import subprocess
import argparse
import requests
import json
import os
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

parser = argparse.ArgumentParser(description='Script to update gateway software')
parser.add_argument('GW_ID', type=str, help='ID of the gateway you are trying to update')

parser.add_argument('--old', action='store_true', help='Updating from 1.4.35 or older')
args = parser.parse_args()
GW = args.GW_ID

Fota_url = 'https://firmware.tagntrac.io/Systech/test/fota.tgz'
api_base = "https://api.tagntrac.io"
token = ""

def login():
    global token
    login_response = requests.post(api_base + "/login?clientId=Tgnztm9b8rac",
                                    headers={"Origin" : "https://demo.tagntrac.io", "Content-Type" : "application/json"},
                                    data=json.dumps({"emailId" : "owen.test1@tagntrac.com", "userSecret" : "T3xp45c0#1"}))
    try:
        if login_response.json()["status"] == "SUCCESS":
            print("Login successful.")
            token = login_response.json()["token"]
        else:
            print(login_response.text)
            print("Login failed. No token found.")
    except Exception as e:
        print(login_response.text)
        print(f"Login failed. No token found. Exception: {str(e)}")


def fota(file_link):
    cmd_response = requests.post(api_base + "/device/" + GW + "/shadow", 
                        headers={"Content-Type" : "application/json", "Authorization" : token},
                        data=json.dumps({"download" : file_link})).text
    print("data = " + json.dumps({"download" : file_link}))
    print(cmd_response)


def reboot():
    cmd_response = requests.post(api_base + "/device/" + GW + "/shadow",
                                 headers={"Content-Type" : "application/json", "Authorization" : token},
                                 data = json.dumps({"local_cmds" : {"gw_reset" : 1}})).text
    print(cmd_response)

def get_shadow():
    cmd_response = requests.get(api_base + "/device/" + GW + "/shadow",
                                headers={"Content-Type" : "application/json", "Authorization" : token}).text
    print(cmd_response) 
    return cmd_response


login()



def update_GW():
    if args.old:
        print(f"Updating Gateway {GW} with old method")
    else:
        print(f"Updating Gateway {GW}")

    fota(Fota_url)
    time.sleep(15)
    reboot()
    time.sleep(180)
    if args.old:
        reboot()
        time.sleep(180)
        fota(Fota_url)
        time.sleep(15)
        reboot()
        time.sleep(180)
        reboot()
    print(f'Gateway {GW} successfully updated')

update_GW()
    

