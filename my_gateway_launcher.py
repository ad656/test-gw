import json
import argparse
import multiprocessing
import os
import re
import requests
import shutil
import subprocess
import sys
import time


parser = argparse.ArgumentParser(description='Description of your script.')	
parser.add_argument('--force', '-f', action='store_true', help='force swaps files from fota folder to home/root')	
args = parser.parse_args()


os.system("hciconfig hci0 down && hciconfig hci0 up")
os.chdir("/home/root")

API_BASE = "https://api.tagntrac.io"
CWD_PATH = "/home/root"
FOTA_PATH = "fota/home/root"
MAX_WAIT = 180 # How long do we wait before giving up on testing if logger_gateway2.py updates the shadow?
REQUIRED_FILES = ["gateway_launcher.sh", "logger_gateway2.py", "logger_utilities.py", "gateway_launcher.py"]

# TODO: add full paho connection here so we don't depend on the API
def login():
    login_response = requests.post(f"{API_BASE}/login?clientId=Tgnztm9b8rac",
                                    headers={"Origin" : "https://demo.tagntrac.io", "Content-Type" : "application/json"},
                                    data=json.dumps({"emailId" : "owen.test1@tagntrac.com", "userSecret" : "T3xp45c0#1"}))
    try:
        if login_response.json()["status"] == "SUCCESS":
            print("Login successful.")
            return login_response.json()["token"]
    except Exception as e:
        print(f"Exception: {str(e)}")
    print(f"Login failed: {login_response.text}")
    return None

def get_shadow(gw_id, token):
    cmd_response = requests.get(f"{API_BASE}/device/{gw_id}/shadow",
                                headers={"Content-Type" : "application/json", "Authorization" : token})
    try:
        if cmd_response.json()["status"] == "SUCCESS":
            print("Got the shadow!")
            return cmd_response.json()["shadow"]
    except Exception as e:
        print(f"Exception: {str(e)}")
    print(f"Could not get the shadow: {cmd_response.text}")
    return None
    
def get_gw_id():
    gwl = open(f"{CWD_PATH}/gateway_launcher.sh").read()
    gw_idx = gwl.find("GW_ID=") + len("GW_ID=")
    if gw_idx == -1:
        print("Could not get gateway ID, something is messed up!")
        return None
    return gwl[gw_idx:gwl.find("\n", gw_idx)]

# Look at every valid network interface and record its IP if it has one
# Output is a dict that looks like { interface0 : ip0 , interface1 : ip1 , ... }
def get_ips():
    ip_dict = {}
    # Ignore useless interfaces like docker0, and lo
    # Known valid interfaces: wlan0, eth0, eth3, rmnet_data0, 
    valid_ifaces = r"(wl.*)|(eth\d+)|(rmnet_data\d+)|(enx.*)"
    ifconfig_out = subprocess.run("ifconfig", shell=True, capture_output=True).stdout.decode().split("\n\n")
    for block in ifconfig_out: # Each block is one network interface
        iface_name = block[ : block.find(" ") ]
        if re.fullmatch(valid_ifaces, iface_name) and "inet addr:" in block: # If the interface is valid and there's an IP address...
            ip_start = block.find("inet addr:") + len("inet addr:")
            ip_dict[iface_name] = block[ ip_start : block.find(" ", ip_start) ] # ... slice out the IP address and put it in the dict
    return ip_dict

def get_lg2_ver(file):
    lg2 = open(file, "r").read()
    major_idx = lg2.find("major = ") + len("major = ")
    major = lg2[ major_idx : lg2.find("\n", major_idx) ]
    minor_idx = lg2.find("minor = ") + len("minor = ")
    minor = lg2[ minor_idx : lg2.find("\n", minor_idx) ]
    release_idx = lg2.find("release = ") + len("release = ")
    release = lg2[ release_idx : lg2.find("\n", release_idx) ]
    return f"{major}.{minor}.{release}"

# Return a list of full paths of all files in the FOTA update
def fota_list(dir):
    files = []
    for fd in os.listdir(dir):
        full_path = f"{dir}/{fd}"
        if os.path.isfile(full_path):
            files.append(full_path)
        if os.path.isdir(full_path):
            files += fota_list(full_path)
    print(f"fota_list: returning {files}")
    return files

def swap():
    for file in REQUIRED_FILES: # Swap only the required files
        print(file)
        contents = open(f"{FOTA_PATH}/{file}").read()
        if os.path.exists(file): # Versions < 1.4.28 don't have gateway_launcher.py
            shutil.copy2(file, f"{FOTA_PATH}")
        open(file, "w").write(contents)
        print(f"Swapped {file} and {FOTA_PATH}/{file}")
    open("STATUS", "w").write("VERIFIED")
    open(f"{FOTA_PATH}/STATUS", "w").write("VERIFIED")


def replacement():
    print("replacement ran")
    if os.path.exists(f"{FOTA_PATH}/STATUS"): # Is this FOTA new, known to work, or known to be bad?
        #fota_status = open(f"{FOTA_PATH}/STATUS").read().replace("\n", "")
        print("STATUS exists")
    else:
        print("Did not find a STATUS file")
        with open(f"{FOTA_PATH}/STATUS","w") as status_file:
            status_file.write("SWAP")
    if not all([os.path.exists(f"{FOTA_PATH}/{rf}") for rf in REQUIRED_FILES]): # FOTA can't run on its own
        print(f"FOTA is invalid, missing required files:\n")
        print(list(filter(lambda f : not os.path.exists(f), [f"{FOTA_PATH}/{rf}" for rf in REQUIRED_FILES])))
        print("Defaulting to normal version...")
    else:
        fota_stat = open(f"{FOTA_PATH}/STATUS", 'r').read()
        print(f"fota_status is {fota_stat}")
        if fota_stat == "SWAP": # Last time we ran this, it worked, so make it the primary version
            print("FOTA image worked last time, performing swap...")
            swap()

        #elif fota_stat == "NEW":
            #print("New FOTA detected!")
            #fota_gwl = open(f"{FOTA_PATH}/gateway_launcher.sh").read() # New gateway_launcher.sh, fill in gateway ID
            # # Intentionally introduce a bug to test fallback
            # open(f"{FOTA_PATH}/logger_gateway2.py", "w").write("AAA")
            #if "@GW_ID@" in fota_gwl:
                #open(f"{FOTA_PATH}/gateway_launcher.sh", "w").write(fota_gwl.replace("@GW_ID@", GW_ID))
               # gwl_path = f"{CWD_PATH}/{FOTA_PATH}"
               # using_fota = True
        #elif fota_stat == "INVALID":
            #print("FOTA is known to be invalid, defaulting to the old version...")

# def run_lg2(gwl_path):
#     gw_proc = subprocess.Popen(["sh", gwl_path], stdout=open("/home/root/logfile.out", "w"), stderr=subprocess.STDOUT)
#     # os.system(f"{gwl_path}/gateway_launcher.sh 2>&1 | tee logfile.out")

def main():
    GW_ID = get_gw_id()
    print(args.force) 
    fota_files = fota_list(f"{CWD_PATH}/fota")
    using_fota = False
    gwl_path = CWD_PATH
    # TODO: abstract launch system so that can be failure-proof too
    for file_path in fota_files: # Copy non-required files to their destinations, no questions asked
        if os.path.basename(file_path) not in REQUIRED_FILES:
            dest_dir = os.path.dirname(file_path[file_path.find("fota") + 4:])
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(file_path, dest_dir)
            print(f"Copied {file_path} to {dest_dir}")
            if os.path.basename(file_path).endswith("service"):
                os.system("systemctl daemon-reload")
    
    if args.force is True:	
        print("force swapping since flag was found")	
        swap()	
    else:    
        print("force flag not found")	
        replacement()

    start_time = time.monotonic()
    token = None
    while time.monotonic() - start_time < MAX_WAIT and token is None:
        try:
            print("Trying to log in...")
            token = login()
            print("Success!")
        except Exception as e:
            print(f"Exception: {str(e)}")
            time.sleep(10)
    print(f"{token=}")
    check_update = True
    if token is None:
        check_update = False
    print(f"{check_update=}")
    new_ver = "NONE"
    if using_fota:
        os.chdir(f"{CWD_PATH}/{FOTA_PATH}")
    print(f"Running {gwl_path}/gateway_launcher.sh...")
    lg2_run1 = subprocess.Popen(["sh", f"{gwl_path}/gateway_launcher.sh"])
    time.sleep(20)
    if check_update:
        new_shadow = get_shadow(GW_ID, token)
        if new_shadow is None:
            print(f"Shadow is None, is the gateway {GW_ID} in AWS?")
        try:
            new_ver = new_shadow["state"]["reported"]["firmware_version"]
        except Exception as e:
            print("Could not get new shadow version!")
        print(f"{new_shadow=}")
        print(f"{new_ver=}")
        print(get_lg2_ver(f"{gwl_path}/logger_gateway2.py"))
        if new_ver.endswith("-DEBUG"):
            new_ver = new_ver[:new_ver.find("-DEBUG")]
        if new_ver == get_lg2_ver(f"{gwl_path}/logger_gateway2.py"): # Whatever we ran is working
            print("Current logger_gateway2.py file updated the shadow!")
            if using_fota: # If it was new, 
                print("Upon next boot, new FOTA version will replace old version.")
                open(f"{CWD_PATH}/{FOTA_PATH}/STATUS", "w").write("SWAP")
        else:
            print("Current logger_gateway2.py file did not update the shadow.")
            if using_fota:
                open(f"{CWD_PATH}/{FOTA_PATH}/STATUS", "w").write("INVALID")
                print("Falling back to the default version...")
                os.system("systemctl restart tagntrac_gateway")
                sys.exit(0)
    # TODO: if main version is not working, fall back to FOTA?
    # while True:
    #     pass
main()
