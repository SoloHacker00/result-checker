import os
import time
import requests
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- SECRETS (Passed from GitHub) ---
# We use environment variables so your passwords aren't public
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
WHATSAPP_API_KEY = os.environ.get("WHATSAPP_API_KEY") 
WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE") # e.g., +919999999999

# --- CONFIG ---
START_ROLL = 7002
END_ROLL = 7069
PRIORITY_ROLL = 7022
PREFIX = "24UECE"
INPUT_BOX_ID = "txtRollNo"
GET_RESULT_BUTTON_ID = "btnGetResult"
EXTERNAL_SCRIPT_NAME = "merge_script.py"

# Setup Paths
BASE_DIR = os.getcwd()
DOWNLOAD_DIR = os.path.join(BASE_DIR, "4th Sem Results")
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # GitHub Actions has no screen
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True 
    }
    chrome_options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=chrome_options)

def send_whatsapp_msg(message):
    """Sends text alert to WhatsApp via CallMeBot"""
    if not WHATSAPP_API_KEY: return
    
    url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={message}&apikey={WHATSAPP_API_KEY}"
    try:
        requests.get(url, timeout=10)
        print("   -> [WhatsApp] Alert sent!")
    except Exception as e:
        print(f"   -> [WhatsApp] Failed: {e}")

def send_telegram_pdf(file_path):
    """Sends PDF to Telegram (WhatsApp API doesn't support free file upload easily)"""
    if not TELEGRAM_BOT_TOKEN: return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': '🎉 Results Declared!'}
            files = {'document': f}
            requests.post(url, files=files, data=data)
            print("   -> [Telegram] PDF Sent!")
    except Exception as e:
        print(f"   -> [Telegram] Error: {e}")

def check_and_download():
    driver = get_driver()
    wait = WebDriverWait(driver, 10)
    
    print(">>> Checking Website...")
    try:
        driver.get("https://mbmiums.in/")
        
        # Navigate
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'ExamResult.aspx')]"))).click()
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'View Semester Results')]"))).click()
            time.sleep(1)
        except: pass
        
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Even') and contains(text(), '2024')]"))).click()
        
        # LOOK FOR THE ECC LINK
        try:
            branch_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'ECE') and (contains(text(), 'IV') or contains(text(), '4th'))]")))
            branch_link.click()
            wait.until(EC.presence_of_element_located((By.ID, INPUT_BOX_ID)))
            print(">>> LINK ACTIVE! Starting Download...")
            
            # Send initial alert
            send_whatsapp_msg("Result Link Found! Downloading now...")
            
            # Download Logic
            roll_sequence = [PRIORITY_ROLL] + [r for r in range(START_ROLL, END_ROLL + 1) if r != PRIORITY_ROLL]
            
            for roll in roll_sequence:
                try:
                    full_roll = f"{PREFIX}{roll}"
                    driver.find_element(By.ID, INPUT_BOX_ID).clear()
                    driver.find_element(By.ID, INPUT_BOX_ID).send_keys(full_roll)
                    driver.find_element(By.ID, GET_RESULT_BUTTON_ID).click()
                    time.sleep(3) # Wait for download
                except: continue

            # Run Merger
            script_full_path = os.path.join(BASE_DIR, EXTERNAL_SCRIPT_NAME)
            
            print(f"   -> Running merger from: {DOWNLOAD_DIR}")
            subprocess.run(["python", script_full_path], cwd=DOWNLOAD_DIR)
            
            # Send Final PDF
            merged_pdf = os.path.join(DOWNLOAD_DIR, "merged_all.pdf")
            if os.path.exists(merged_pdf):
                send_telegram_pdf(merged_pdf)
                send_whatsapp_msg("Merged PDF sent to Telegram!")
            
            return True # Success
            
        except TimeoutException:
            print(">>> Link not active yet.")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":

    check_and_download()

