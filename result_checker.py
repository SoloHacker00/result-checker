import os
import time
import requests
import subprocess
import traceback  # <--- NEW: To print exact errors
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIG ---
START_ROLL = 9002
END_ROLL = 9069
PRIORITY_ROLL = 9022
PREFIX = "24UEEE"
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
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
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
    wait = WebDriverWait(driver, 30)
    
    print(">>> DIAGNOSTIC MODE: STARTED")
    try:
        print("   -> Loading Homepage...")
        driver.get("https://mbmiums.in/")
        
        # 1. Click 'Exam Results'
        print("   -> Attempting to click 'Exam Results'...")
        el_results = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'ExamResult.aspx')]")))
        driver.execute_script("arguments[0].click();", el_results)
        
        # 2. Click 'View Semester Results'
        try:
            print("   -> Attempting to click 'View Semester Results'...")
            el_cat = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'View Semester Results')]")))
            driver.execute_script("arguments[0].click();", el_cat)
            time.sleep(2)
        except: 
            print("   -> [INFO] 'View Semester Results' might be open already.")

        # 3. Click 'Even Sem 2024'
        print("   -> Attempting to click 'Even Sem 2024'...")
        # Note: Broadened xpath to just 2024 just in case
        el_sem = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Even') and contains(text(), '2024')]")))
        driver.execute_script("arguments[0].click();", el_sem)
        
        # 4. SEARCHING FOR BRANCH
        print("   -> Searching for Electrical/EEE Link...")
        
        branch_xpath = "//a[(contains(text(), 'Electronics & Electrical') or contains(text(), 'EEE')) and (contains(text(), 'IV') or contains(text(), '4th'))]"
        
        try:
            el_branch = wait.until(EC.presence_of_element_located((By.XPATH, branch_xpath)))
            print(f"   -> FOUND LINK: '{el_branch.text}'")
            driver.execute_script("arguments[0].click();", el_branch)
        except Exception:
            # --- DIAGNOSTIC BLOCK ---
            print("\n" + "!"*30)
            print("   -> [ERROR] COULD NOT FIND BRANCH LINK!")
            print("   -> Dumping all visible links to see what is wrong:")
            print("!"*30)
            
            links = driver.find_elements(By.TAG_NAME, "a")
            for l in links:
                txt = l.text.strip()
                if len(txt) > 3: # Only print meaningful links
                    print(f"      [LINK]: {txt}")
            
            raise Exception("Branch Link not found (See list above for available options)")

        # Verify Input Box
        print("   -> Waiting for Input Box...")
        wait.until(EC.presence_of_element_located((By.ID, INPUT_BOX_ID)))
        
        print(">>> LINK ACTIVE! Starting Processing...")
        send_telegram("🚨 Result Link Active! Starting downloads...")

        # Download Logic
        roll_sequence = [PRIORITY_ROLL] + [r for r in range(START_ROLL, END_ROLL + 1) if r != PRIORITY_ROLL]
        
        for roll in roll_sequence:
            try:
                full_roll = f"{PREFIX}{roll}"
                driver.find_element(By.ID, INPUT_BOX_ID).clear()
                driver.find_element(By.ID, INPUT_BOX_ID).send_keys(full_roll)
                
                btn = driver.find_element(By.ID, "btnGetResult")
                driver.execute_script("arguments[0].click();", btn)
                
                time.sleep(5) 

                if roll == PRIORITY_ROLL:
                    files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.pdf')]
                    if files:
                        newest_pdf = max(files, key=os.path.getctime)
                        send_telegram("Here is your personal result! 👇", newest_pdf)

            except Exception as e: 
                print(f"   -> Skipped {roll}: {e}")
                continue

        # Merge
        print("   -> Merging...")
        script_full_path = os.path.join(BASE_DIR, EXTERNAL_SCRIPT_NAME)
        subprocess.run(["python", script_full_path], cwd=DOWNLOAD_DIR)
        
        merged_pdf = os.path.join(DOWNLOAD_DIR, "merged_all.pdf")
        if os.path.exists(merged_pdf):
            send_telegram("Full Class Result:", merged_pdf)
        else:
            send_telegram("Downloads done, merge failed.")

        disable_github_workflow()
        return True
        
    except Exception:
        print("\n" + "#"*40)
        print(">>> FATAL ERROR OCCURRED")
        print("#"*40)
        # THIS PRINTS THE EXACT LINE NUMBER AND ERROR
        traceback.print_exc()
        
        # Save artifacts
        driver.save_screenshot("error_screenshot.png")
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
            
        print(">>> Artifacts saved: error_screenshot.png, debug_page.html")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    check_and_download()

