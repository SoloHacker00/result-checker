import os
import time
import requests
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIG ---
START_ROLL = 8002
END_ROLL = 8069
PRIORITY_ROLL = 8022
PREFIX = "24UECC"
INPUT_BOX_ID = "txtRollNo"
EXTERNAL_SCRIPT_NAME = "merge_script.py"

# --- SECRETS ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAME = os.environ.get("GITHUB_REPOSITORY") 

# Setup Paths
BASE_DIR = os.getcwd()
DOWNLOAD_DIR = os.path.join(BASE_DIR, "4th Sem Results")
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

def get_driver():
    chrome_options = Options()
    # 1. Run Headless
    chrome_options.add_argument("--headless=new")
    
    # 2. Set Window Size (CRITICAL: Prevents mobile layout)
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 3. Spoof User Agent (Look like a real Windows PC)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 4. Standard bypasses
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    prefs = {"download.default_directory": DOWNLOAD_DIR, "plugins.always_open_pdf_externally": True}
    chrome_options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=chrome_options)

def send_telegram(msg, file_path=None):
    if not TELEGRAM_BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/"
    try:
        if file_path:
            with open(file_path, 'rb') as f:
                requests.post(url + "sendDocument", files={'document': f}, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': msg})
        else:
            requests.post(url + "sendMessage", data={'chat_id': TELEGRAM_CHAT_ID, 'text': msg})
    except Exception as e: print(f"Telegram Error: {e}")

def disable_github_workflow():
    if not GITHUB_TOKEN or not REPO_NAME: return
    url = f"https://api.github.com/repos/{REPO_NAME}/actions/workflows/main.yml/disable"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    requests.put(url, headers=headers)

def check_and_download():
    driver = get_driver()
    # INCREASED TIMEOUT: 30 Seconds
    wait = WebDriverWait(driver, 30)
    
    print(">>> Checking Website...")
    try:
        driver.get("https://mbmiums.in/")
        
        # 1. Click 'Exam Results'
        print("   -> Clicking Exam Results...")
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'ExamResult.aspx')]"))).click()
        
        # 2. Click 'View Semester Results' (Handle if it's already open)
        try:
            print("   -> Checking Category Tab...")
            cat_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'View Semester Results')]")))
            cat_link.click()
            time.sleep(2)
        except: 
            print("   -> Tab might be already open, proceeding...")

        # 3. Click 'Odd Sem 2024'
        print("   -> Clicking Odd Sem 2024...")
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Odd') and contains(text(), '2024')]"))).click()
        
        # 4. CHECK FOR ECC LINK
        print("   -> Searching for ECC Link...")
        try:
            branch_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'ECC') and (contains(text(), 'III') or contains(text(), '3rd'))]")))
            branch_link.click()
            
            # Verify Input Box Exists
            wait.until(EC.presence_of_element_located((By.ID, INPUT_BOX_ID)))
            
            print(">>> LINK FOUND! Starting processing...")
            send_telegram("🚨 Result Link Active! Starting downloads...")

            # Download Logic
            roll_sequence = [PRIORITY_ROLL] + [r for r in range(START_ROLL, END_ROLL + 1) if r != PRIORITY_ROLL]
            
            for roll in roll_sequence:
                try:
                    full_roll = f"{PREFIX}{roll}"
                    driver.find_element(By.ID, INPUT_BOX_ID).clear()
                    driver.find_element(By.ID, INPUT_BOX_ID).send_keys(full_roll)
                    driver.find_element(By.ID, "btnGetResult").click()
                    time.sleep(5) # Give 5 seconds for download

                    # Priority Send
                    if roll == PRIORITY_ROLL:
                        files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.pdf')]
                        if files:
                            newest_pdf = max(files, key=os.path.getctime)
                            send_telegram("Here is your personal result! 👇", newest_pdf)

                except Exception: continue

            # Merge
            script_full_path = os.path.join(BASE_DIR, EXTERNAL_SCRIPT_NAME)
            subprocess.run(["python", script_full_path], cwd=DOWNLOAD_DIR)
            
            merged_pdf = os.path.join(DOWNLOAD_DIR, "merged_all.pdf")
            if os.path.exists(merged_pdf):
                send_telegram("Full Class Result:", merged_pdf)
            else:
                send_telegram("Downloads done, merge failed.")

            disable_github_workflow()
            return True
            
        except TimeoutException:
            print(">>> Link not active yet (Timeout checking for ECC link).")
            return False

    except Exception as e:
        # --- DEBUG: TAKE SCREENSHOT ON ERROR ---
        print(f"Error: {e}")
        driver.save_screenshot("error_screenshot.png")
        print(">>> Screenshot saved as error_screenshot.png")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    check_and_download()
