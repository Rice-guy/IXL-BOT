import os
import re
import tempfile
import time

import pyautogui as pyi
from google import genai
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException


GEMINI_API_KEY = "apikeyhere"
IXL_USERNAME   = input("Enter IXL username: ")
IXL_PASSWORD   = input("Enter IXL password: ")

GEMINI_MODEL   = "gemini-2.5-flash-preview-09-2025"
GEMINI_PROMPT  = (
    "Answer the math problem in the image. "
    "Only provide the answer and nothing else. "
    "Write fractions in this format: 1/2, 2/3, 3/5. "
    "Do not include curly braces {} in any answer."
)

CHROMEDRIVER_PATH = "chromedriver.exe"

WAIT_TIMEOUT     = 10  
EXPONENT_PATTERN = re.compile(r"(\^\d+)")


def create_driver():
    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver  = webdriver.Chrome(service=service)
    screen_w, screen_h = pyi.size()
    driver.set_window_size(screen_w, screen_h)
    return driver


def wait_for(driver, by, value, timeout = WAIT_TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, value))
    )


def wait_clickable(driver, by, value, timeout = WAIT_TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )


def login(driver):
   
    driver.get("https://www.ixl.com/signin")
    wait_for(driver, By.ID, "siusername").send_keys(IXL_USERNAME)
    driver.find_element(By.ID, "sipassword").send_keys(IXL_PASSWORD)
    wait_clickable(driver, By.ID, "signin-button").click()
    
    WebDriverWait(driver, WAIT_TIMEOUT).until(
        lambda d: "signin" not in d.current_url
    )


def dismiss(driver):
    try:
        driver.find_element(
            By.XPATH,
            "//h2[contains(@class,'feedback-header correct') and text()='Sorry, incorrect...']"
        )
        got_it = driver.find_element(
            By.XPATH,
            "//button[contains(@class,'crisp-button') and text()='Got it']"
        )
        got_it.click()
        return True
    except NoSuchElementException:
        return False


def find_textbox(driver):
    for class_name in ("proxy-input", "fillIn"):
        try:
            return driver.find_element(By.CLASS_NAME, class_name)
        except NoSuchElementException:
            continue
    return None


def find_submit_button(driver):
    try:
        return wait_clickable(
            driver, By.XPATH,
            "//button[normalize-space(@class)='crisp-button' and text()='Submit']",
            timeout=3
        )
    except TimeoutException:
        return None


def take_screenshot():
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    pyi.screenshot(tmp.name, region=(100, 200, 1400, 800))
    return tmp.name



def format_math_expr(expression):
    return EXPONENT_PATTERN.sub(r"\1 ", expression)


def ask_gemini(gemini_client, screenshot_path) -> str:
    uploaded = gemini_client.files.upload(file=screenshot_path)
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[GEMINI_PROMPT, uploaded]
    )
    return response.text.strip()


def solve_loop(driver, gemini_client):
    print("Solver running — press Ctrl+C to stop.")

    while True:
        try:
      
            if dismiss(driver):
                continue

            
            submit_button = find_submit_button(driver)
            if submit_button is None:
                continue

            
            textbox = find_textbox(driver)
            if textbox is None:
                print("Warning: could not find a textbox. Skipping this question.")
                continue

            
            screenshot_path = take_screenshot()
            try:
                raw_answer = ask_gemini(gemini_client, screenshot_path)
            finally:
                os.unlink(screenshot_path)   

            answer = format_math_expr(raw_answer)
            print(f"Gemini answer: {answer!r}")

            
            textbox.clear()
            textbox.send_keys(answer)
            submit_button.click()

        except KeyboardInterrupt:
            print("\nStopping.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)



def main():
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    driver = create_driver()

    try:
        login(driver)

        ixl_url = input("Enter desired IXL URL: ").strip()
        driver.get(ixl_url)

        solve_loop(driver, gemini_client)

    finally:
        driver.quit()
        print("Session ended.")
