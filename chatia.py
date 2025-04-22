import pyautogui
import pyperclip
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
# Import WebDriverWait and expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
# Import datetime for timestamp comparison
from datetime import datetime


# --- Helper Function Definitions ---

def find_and_click_latest_log(driver, wait):
    """Finds the 'Agent Logs' section, parses timestamps, and clicks the button with the latest timestamp."""
    print("  Finding and clicking button with the latest timestamp under 'Agent Logs'...")
    container_div_xpath = "//h2[normalize-space(.)='Agent Logs']/following-sibling::div[@class='space-y-2']"
    # Wait for at least one button to be present in the container
    first_button_in_container_xpath = f"({container_div_xpath}//button)[1]"
    try:
        print(f"  - Waiting for first button presence using XPath: {first_button_in_container_xpath}")
        wait.until(EC.presence_of_element_located((By.XPATH, first_button_in_container_xpath)))
        print("  - At least one button found within 'Agent Logs' container.")

        container_div = driver.find_element(By.XPATH, container_div_xpath)
        buttons_in_div = container_div.find_elements(By.XPATH, ".//button")

        if not buttons_in_div:
            print("  Error: No buttons found within the 'Agent Logs' div after waiting.")
            return False

        latest_timestamp = None
        button_to_click = None
        print(f"  - Found {len(buttons_in_div)} button(s). Parsing timestamps...")
        for button in buttons_in_div:
            try:
                timestamp_div = button.find_element(By.XPATH, ".//div[@class='text-sm text-muted-foreground']")
                timestamp_str_raw = timestamp_div.text
                # Clean the string
                timestamp_str_clean = timestamp_str_raw.replace(u'\xa0', ' ').strip()
                if timestamp_str_clean.endswith('.'):
                    timestamp_str_clean = timestamp_str_clean[:-1].strip()

                # Parse the timestamp
                current_timestamp = datetime.strptime(timestamp_str_clean, "%d/%m/%Y, %H:%M:%S")
                print(f"    - Parsed timestamp: {current_timestamp} from string '{timestamp_str_raw}'")

                if latest_timestamp is None or current_timestamp > latest_timestamp:
                    latest_timestamp = current_timestamp
                    button_to_click = button
                    print(f"      - New latest timestamp found.")

            except NoSuchElementException:
                print(f"    - Warning: Could not find timestamp div for a button.")
            except ValueError as ve:
                print(f"    - Warning: Could not parse timestamp string '{timestamp_str_clean}'. Error: {ve}")
            except Exception as ex:
                print(f"    - Warning: An unexpected error occurred processing a button timestamp. Error: {ex}")

        if button_to_click:
            button_title = button_to_click.get_attribute('title')
            print(f"  Found latest timestamp ({latest_timestamp}). Clicking button with title '{button_title}'.")
            # Ensure the button is clickable before clicking
            wait.until(EC.element_to_be_clickable(button_to_click))
            button_to_click.click()
            return True
        else:
            print("  Error: Could not determine button with the latest timestamp (parsing failed or no valid buttons found).")
            return False

    except TimeoutException:
        print(f"  Error: Timed out waiting for the first button in 'Agent Logs' (XPath: {first_button_in_container_xpath}).")
        return False
    except NoSuchElementException as e:
        print(f"  Error finding elements in find_and_click_latest_log: {e}")
        return False
    except Exception as e:
        print(f"  An unexpected error occurred during find_and_click_latest_log: {e}")
        return False

def scrape_latest_response(driver, wait):
    """Finds the last response div and scrapes formatted text from its child elements."""
    print("  Finding the last relevant div container and scraping formatted text...")
    # XPath targets the last main response container div, preferring 'prose' class
    primary_div_xpath = "(//div[contains(@class, 'prose')])[last()]"
    # Fallback if 'prose' isn't found (previous XPath)
    fallback_div_xpath = "(//div[contains(@class, 'p-4') and contains(@class, 'rounded-lg') and contains(@class, 'border') and contains(@class, 'bg-background')])[last()]"

    element_div = None
    try:
        # Try finding the 'prose' div first
        try:
            print(f"  - Attempting to find main response div with XPath: {primary_div_xpath}")
            element_div = wait.until(EC.presence_of_element_located((By.XPATH, primary_div_xpath)))
            print("  - Found 'prose' container div.")
        except TimeoutException:
            print(f"  - 'prose' div not found. Trying fallback XPath: {fallback_div_xpath}")
            element_div = wait.until(EC.presence_of_element_located((By.XPATH, fallback_div_xpath)))
            print("  - Found fallback container div.")

        print("  - Extracting text from child elements...")
        # Get all direct children elements of the container
        # Using '*' selects all element types. We rely on .text to get content recursively.
        child_elements = element_div.find_elements(By.XPATH, "./*")

        if not child_elements:
             # If no direct children, get the text of the container itself
             print("  Warning: No direct child elements found in the container. Getting container's text directly.")
             scraped = element_div.text.strip()
        else:
            # Extract text from each direct child element.
            # Selenium's .text should handle nested elements (strong, code) and pre formatting.
            all_texts = []
            for child in child_elements:
                 child_text = child.text
                 if child_text is not None: # Ensure text exists
                     all_texts.append(child_text.strip()) # Add stripped text

            # Join the texts from child elements with double newlines for separation
            # Filter out potential empty strings resulting from non-text elements or empty elements
            scraped = "\n\n".join(filter(None, all_texts))

        if scraped is None: # Should not happen easily now
             print("  Warning: Combined scraped text is None.")
             return None # Indicate failure clearly
        elif not scraped:
             print("  Warning: Combined scraped text is empty (container or children might lack text).")
             return "" # Return empty string if that's acceptable
        else:
            print(f"  Successfully scraped formatted text: '{scraped[:100]}...'") # Increased preview length
            return scraped

    except TimeoutException:
        # This catches timeout for both primary and fallback XPaths if element_div is still None
        print(f"  Error: Timed out waiting for response container div (tried primary XPath: '{primary_div_xpath}' and fallback: '{fallback_div_xpath}').")
        return None
    except NoSuchElementException as e:
        # This might happen if the container is found but find_elements fails, though less likely with "./*"
        print(f"  Error finding child elements during scrape_latest_response: {e}")
        return None
    except Exception as e:
        print(f"  An unexpected error occurred during scrape_latest_response: {e}")
        return None

def find_and_click_chat_button_by_hash(driver, wait, chat_hash):
    """Finds and clicks the specific chat button based on its text (hash)."""
    print(f"  Attempting to find and click button specifically for chat hash: '{chat_hash}'")
    if not chat_hash:
        print("  Error: chat_hash is empty. Cannot find button.")
        return False

    # Precise XPath using the hash stored earlier
    button_xpath = f"//tbody/tr[td[2]/span[normalize-space(.)='No folder']]/td[1]/button[normalize-space(text())='{chat_hash}']"
    tag_selector = (By.XPATH, button_xpath)
    try:
        element = wait.until(EC.element_to_be_clickable(tag_selector))
        print(f"  Found button via hash '{chat_hash}'. Clicking.")
        element.click()
        return True
    except TimeoutException:
        print(f"  Error: Timed out waiting for button with specific hash '{chat_hash}' (XPath: {button_xpath}).")
        return False
    except Exception as e:
        print(f"  Error clicking button with hash '{chat_hash}': {e}")
        return False

# --- Placeholder for Text to Insert ---
text_to_insert = "Hello, please present yourself as if you were starting a conversation with a person you're just meeting for the first time. Be friendly and engaging, and try to keep the conversation going. Make sure to try to get to know the other person as much as possible. Remember you're trying to have a CONVERSATION with them. Make sure to ask them questions and get to know them as much as possible, and explicitly express your intentions to have a CONVERSATION/DISCUSSION with them. Keep in mind that this interaction will last more than one turn, just like in real life where people have conversations with multiple exchanges. If you are caught in a loop of some kind, try to change the topic to keep the conversation going."
#text_to_insert = "Hello. Please write the number 1 and then ask to please keep going with the numerical sequence from 2"
scraped_text = "" # Will hold the text scraped in step 11 and later overwritten in step 25
chat1_hash = "" # Initialize variable to store button text from first round
chat2_hash = "" # Initialize variable to store button text from second round

# --- New Sequence Start ---
try:
    print("Starting new action sequence...")

    # --- Steps 1-7: Initial PyAutoGUI actions ---
    print("Step 1: Opening Window A (Chat 1)... (Ctrl+Shift+N)")
    pyautogui.hotkey('ctrl', 'shift', 'n')
    time.sleep(3)

    print("Step 2: Focusing Chat 1 and Opening Chat Interface... (Ctrl+L)")
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(3)

    # --- New Step: Prompt user to select model ---
    print("Prompting user to select model for Chat 1...")
    pyautogui.alert(
        text="Please select cursor-small or o4-mini for CHAT 1 within the next 15 seconds",
        title="Model Selection Required (Chat 1)",
        button="OK"
    )
    print("Waiting 15 seconds for model selection...")
    time.sleep(15)
    # --- End New Step ---

    print("Step 3: Opening Chat 1 Mode Menu... (Ctrl+Alt+.)")
    pyautogui.hotkey('ctrl', 'alt', '.')
    time.sleep(3)

    print("Step 4: Selecting 'Ask' option for Chat 1...")
    pyautogui.press('down')
    time.sleep(3)

    print("Step 5: Confirming 'Ask' option for Chat 1...")
    pyautogui.press('enter')
    time.sleep(3)

    print(f"Step 6: Inserting initial text into Chat 1: '{text_to_insert[:50]}...'")
    pyperclip.copy(text_to_insert)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(3)

    print("Step 7: Sending Prompt to Chat 1...")
    pyautogui.press('enter')
    time.sleep(10) # Wait for initial response generation


    # --- Initial Selenium Setup ---
    try:
        print("Setting up ChromeDriver...")
        service = ChromeService(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        # Add options if needed, e.g., options.add_argument("--headless")
        driver = webdriver.Chrome(service=service, options=options)
        driver.maximize_window()
        print("ChromeDriver setup complete.")
        time.sleep(3)
    except Exception as e:
        print(f"Error setting up Selenium or opening Chrome: {e}")
        pyautogui.alert(f"Error setting up Selenium: {e}", "Error")
        exit()

    # --- Step 8: Open Browser Page ---
    print("Step 8: Opening http://localhost:3000/chat...")
    driver.get("http://localhost:3000/chat")
    time.sleep(3) # Allow page to load initially

    # --- Steps 9-11: Selenium Actions (First Pass - Interact with Chat 1 Log) ---
    print("Starting Selenium interaction (First Pass - Get Chat 1 initial response)...")
    wait = WebDriverWait(driver, 20) # Define wait time

    # Step 9: Find first 'tr' with 'No folder', get its button text (hash), and click it.
    print("Step 9: Looking for the first 'No folder' row (should be Chat 1's) and clicking its chat button...")
    button_xpath_step_9 = "(//tbody/tr[td[2]/span[normalize-space(.)='No folder']]/td[1]/button)[1]"
    tag_selector_step_9 = (By.XPATH, button_xpath_step_9)
    try:
        element_step_9 = wait.until(EC.element_to_be_clickable(tag_selector_step_9))
        chat1_hash = element_step_9.text # Get the unique text/hash for Chat 1's button
        if chat1_hash:
            print(f"Step 9: Found button for Chat 1 with text '{chat1_hash}'. Storing hash.")
        else:
            print("Step 9: Warning - Found Chat 1 button, but its text is empty. Hash comparison might fail later.")
            # Consider adding a fallback or raising an error if the hash is crucial and empty
        element_step_9.click()
        print("Step 9: Chat 1 button clicked successfully.")
        time.sleep(3)
    except TimeoutException:
        print(f"Error: Timed out waiting for the button in Step 9 (XPath: {tag_selector_step_9[1]}). Is the 'No folder' row present?")
        raise
    except Exception as e:
        print(f"Error during Step 9: {e}")
        raise

    # Step 9.5: Click button with the latest timestamp in Chat 1's log
    print("Step 9.5: Clicking latest log entry for Chat 1...")
    time.sleep(3) # Short delay before next action
    if not find_and_click_latest_log(driver, wait):
        print("Error: Failed Step 9.5 - Could not click the latest log entry for Chat 1.")
        raise Exception("Failed to click latest log in Step 9.5")
    time.sleep(3) # Wait for content to load after click

    # Steps 10 & 11 combined: Scrape text from the latest response
    print("Step 10/11: Scraping Chat 1's latest response...")
    scraped_text = scrape_latest_response(driver, wait)
    if scraped_text is None: # Check for None explicitly
        print("Error: Failed Step 10/11 - Could not scrape Chat 1's response.")
        raise Exception("Failed to scrape response in Step 10/11")
    elif not scraped_text:
         print("Warning: Scraped text for Step 11 is empty.")
         # Decide how to handle empty text - raise error or proceed?
         # raise ValueError("Scraped text is empty in Step 11.") # Optional: Treat empty as error
    else:
        print(f"Step 11: Successfully scraped text from Chat 1: '{scraped_text[:50]}...'")
    time.sleep(3)

    # --- Steps 12-20: PyAutoGUI actions to set up Chat 2 and send Chat 1's response ---
    print("Starting PyAutoGUI sequence for Chat 2 setup...")

    print("Step 12: Returning to Cursor (presumably Chat 1 window)... (Alt+Tab)")
    # Assumption: Alt+Tab from Chrome switches back to the last used app (Chat 1)
    pyautogui.hotkey('alt', 'tab')
    time.sleep(3)

    # Step 13: Optional navigation in Chat 1 window - Keeping as per original
    # print("Step 13: Sending Up Arrow in Chat 1 window...")
    # pyautogui.press('up')
    # time.sleep(1)
    print("Step 13: Skipped (Up Arrow)")
    pyautogui.hotkey('up')

    print("Step 14: Opening Window B (Chat 2)... (Ctrl+Shift+N)")
    pyautogui.hotkey('ctrl', 'shift', 'n')
    time.sleep(10) # Wait for new window

    print("Step 15: Focusing Chat 2 and Opening Chat Interface... (Ctrl+L)")
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(3)

    print("Step 16: Opening Chat 2 Mode Menu... (Ctrl+Alt+.)")
    pyautogui.hotkey('ctrl', 'alt', '.')
    time.sleep(3)

    print("Step 17: Selecting 'Ask' option for Chat 2...")
    pyautogui.press('down')
    time.sleep(3)

    print("Step 18: Confirming 'Ask' option for Chat 2...")
    pyautogui.press('enter')
    time.sleep(3)

    print("Step 19: Pasting Chat 1's scraped text into Chat 2...")
    if scraped_text is None: # Check if scraping failed
        print("Error: Cannot paste, scraped text from Step 11 is None.")
        raise ValueError("Cannot perform Step 19, scraped_text is None.")
    pyperclip.copy(scraped_text)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(3)

    print("Step 20: Sending Prompt to Chat 2...")
    pyautogui.press('enter')
    time.sleep(10) # Wait for Chat 2's first response

    # --- Steps 21-25: Selenium Actions (Second Pass - Interact with Chat 2 Log) ---
    print("Starting Selenium interaction (Second Pass - Get Chat 2 response)...")

    print("Step 21: Switching Window to Chrome...")
    # Assumption: Alt+Tab+Tab from Chat 2 switches to Chrome (Chat 1 -> Chrome -> Chat 2 cycle)
    pyautogui.keyDown('alt')
    time.sleep(3)
    pyautogui.press('tab')
    time.sleep(3)
    pyautogui.press('tab')
    time.sleep(3)
    pyautogui.keyUp('alt')
    time.sleep(3)

    print("Step 22: Reloading browser page to see Chat 2 entry...")
    driver.get("http://localhost:3000/chat")
    time.sleep(5) # Allow time for page reload and elements to render

    # Step 23: Find the *new* 'No folder' row (should be Chat 2), get its hash, click it.
    print("Step 23: Looking for the new 'No folder' row (should be Chat 2) and clicking its chat button...")
    # Find the first button within a 'No folder' row whose text does NOT match chat1_hash
    if not chat1_hash:
        # Fallback or error if chat1_hash wasn't captured correctly
        print("Error: Cannot execute Step 23 reliably as chat1_hash is empty.")
        raise ValueError("chat1_hash is empty, cannot proceed with Step 23 XPath.")

    # Construct XPath to find the first button in a 'No folder' row that doesn't match chat1_hash
    button_xpath_step_23 = (
        f"//tbody/tr[td[2]/span[normalize-space(.)='No folder']]"
        f"/td[1]/button[normalize-space(text()) != '{chat1_hash}'][1]"
    )
    tag_selector_step_23 = (By.XPATH, button_xpath_step_23)

    try:
        print(f"  - Using XPath: {button_xpath_step_23}")
        element_step_23 = wait.until(EC.element_to_be_clickable(tag_selector_step_23))
        chat2_hash = element_step_23.text # Get the unique text/hash for Chat 2's button

        if chat2_hash:
            print(f"Step 23: Found button for Chat 2 with text '{chat2_hash}' (different from Chat 1). Storing hash.")
        else:
            # This case might occur if the button exists but has no text.
            print("Step 23: Warning - Found Chat 2 button, but its text is empty.")

        element_step_23.click()
        print("Step 23: Chat 2 button clicked successfully.")
        time.sleep(3)
    except TimeoutException:
        # Added more detail to the error message
        print(f"Error: Timed out waiting for the button in Step 23.")
        print(f"  - Searched for XPath: {button_xpath_step_23}")
        print(f"  - This means no 'No folder' button could be found whose text was not '{chat1_hash}'.")
        raise
    except Exception as e:
        print(f"Error during Step 23: {e}")
        raise

    # Step 24: Click button with the latest timestamp in Chat 2's log
    print("Step 24: Clicking latest log entry for Chat 2...")
    time.sleep(3)
    if not find_and_click_latest_log(driver, wait):
        print("Error: Failed Step 24 - Could not click the latest log entry for Chat 2.")
        raise Exception("Failed to click latest log in Step 24")
    time.sleep(3)

    # Step 25: Scrape text from Chat 2's latest response
    print("Step 25: Scraping Chat 2's latest response...")
    scraped_text = scrape_latest_response(driver, wait) # Overwrite scraped_text
    if scraped_text is None:
        print("Error: Failed Step 25 - Could not scrape Chat 2's response.")
        raise Exception("Failed to scrape response in Step 25")
    elif not scraped_text:
         print("Warning: Scraped text for Step 25 is empty.")
         # raise ValueError("Scraped text is empty in Step 25.") # Optional
    else:
        print(f"Step 25: Successfully scraped text from Chat 2: '{scraped_text[:50]}...'")
    time.sleep(3)

    # --- Step 26-29: Send Chat 2's response back to Chat 1 ---
    print("Step 26: Switching Window back to Chat 1...")
    # Assumption: Alt+Tab+Tab from Chrome switches to Chat 1 (Chat 2 -> Chrome -> Chat 1 cycle)
    pyautogui.keyDown('alt')
    time.sleep(3)
    pyautogui.press('tab')
    time.sleep(3)
    pyautogui.press('tab')
    time.sleep(3)
    pyautogui.keyUp('alt')
    time.sleep(3)

    # Step 27: Optional navigation - Keeping as per original
    print("Step 27: Sending Down Arrow in Chat 1 window...")
    pyautogui.press('down')
    time.sleep(3)

    print("Step 28: Pasting Chat 2's scraped text into Chat 1...")
    if scraped_text is None:
        print("Error: Cannot paste, scraped text from Step 25 is None.")
        raise ValueError("Cannot perform Step 28, scraped_text is None.")
    pyperclip.copy(scraped_text)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(3)

    print("Step 29: Sending Prompt to Chat 1...")
    pyautogui.press('enter')
    time.sleep(10) # Wait for Chat 1 to process

    # --- Step 30-31: Switch back to Chrome and reload ---
    print("Step 30: Switching Window to Chrome...")
    # Assumption: Alt+Tab from Chat 1 switches to Chrome
    pyautogui.hotkey('alt', 'tab')
    time.sleep(3)

    print("Step 31: Reloading browser page before starting loop...")
    driver.get("http://localhost:3000/chat")
    time.sleep(5) # Allow page to reload

    # --- Infinite Conversation Loop ---
    print("\n"+"="*20 + " STARTING INFINITE CONVERSATION LOOP " + "="*20)
    current_turn_target = "chat2" # Start by sending Chat 1's latest response (from step 29) to Chat 2
    is_first_loop_switch = True # Flag for the initial window switch

    while True:
        print(f"\n--- Loop Turn: Sending to {current_turn_target.upper()} ---")

        # Determine source and target based on the current turn
        if current_turn_target == "chat2":
            source_chat_name = "Chat 1"
            source_chat_hash = chat1_hash
            target_chat_name = "Chat 2"
            pre_paste_nav = [] # No down/up arrow needed for Chat 2?
        else: # Target is chat1
            source_chat_name = "Chat 2"
            source_chat_hash = chat2_hash
            target_chat_name = "Chat 1"
            pre_paste_nav = ['down'] # Send Down arrow as per original Step 27 logic for Chat 1

        # Define window switching keys based on the new rules
        if is_first_loop_switch:
            # Special case for the very first switch (Chrome -> Chat 2)
            switch_keys_to_target = ['alt', 'tab', 'tab']
            # Subsequent switch (Chat 2 -> Chrome) follows the standard rule
            switch_keys_to_chrome = ['alt', 'tab']
            print("  (First loop switch: Using Alt+Tab+Tab to reach target)")
            is_first_loop_switch = False # Clear the flag after the first iteration
        else:
            # Standard switching logic for all subsequent turns
            switch_keys_to_target = ['alt', 'tab', 'tab'] # Chrome -> Chat (1 or 2)
            switch_keys_to_chrome = ['alt', 'tab']      # Chat (1 or 2) -> Chrome

        # 1. In Chrome: Find Source Chat's button, click it, click latest log, scrape response
        print(f"Locating {source_chat_name}'s history in Chrome...")
        if not find_and_click_chat_button_by_hash(driver, wait, source_chat_hash):
            print(f"Error: Failed to find/click button for {source_chat_name} using hash '{source_chat_hash}'.")
            raise Exception(f"Loop Error: Failed to find/click {source_chat_name} button.")
        time.sleep(3)

        print(f"Clicking latest log entry for {source_chat_name}...")
        if not find_and_click_latest_log(driver, wait):
            print(f"Error: Failed to click latest log entry for {source_chat_name}.")
            raise Exception(f"Loop Error: Failed to click latest log for {source_chat_name}.")
        time.sleep(3)

        print(f"Scraping {source_chat_name}'s latest response...")
        scraped_text = scrape_latest_response(driver, wait)
        if scraped_text is None:
            print(f"Error: Failed to scrape {source_chat_name}'s response.")
            raise Exception(f"Loop Error: Failed to scrape {source_chat_name}'s response.")
        elif not scraped_text:
             print(f"Warning: Scraped empty response from {source_chat_name}.")
        else:
             print(f"Scraped from {source_chat_name}: '{scraped_text[:50]}...'")
        time.sleep(3)

        # 2. Switch to Target Chat window and send the response
        print(f"Switching to {target_chat_name} window...")
        if len(switch_keys_to_target) == 2: # Simple Alt+Tab (Shouldn't happen with new logic, but kept for safety)
             pyautogui.hotkey(switch_keys_to_target[0], switch_keys_to_target[1])
        elif len(switch_keys_to_target) == 3: # Alt+Tab+Tab
             pyautogui.keyDown(switch_keys_to_target[0])
             time.sleep(3)
             pyautogui.press(switch_keys_to_target[1])
             time.sleep(3)
             pyautogui.press(switch_keys_to_target[2])
             time.sleep(3)
             pyautogui.keyUp(switch_keys_to_target[0])
        else:
            print(f"Error: Unsupported key sequence for switching windows: {switch_keys_to_target}")
            raise Exception("Loop Error: Invalid window switch sequence.")
        time.sleep(3)

        # Optional navigation before pasting
        for key in pre_paste_nav:
            print(f"Sending '{key}' key...")
            pyautogui.press(key)
            time.sleep(3)

        print(f"Pasting scraped text into {target_chat_name}...")
        pyperclip.copy(scraped_text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(3)

        print(f"Sending Prompt to {target_chat_name}...")
        pyautogui.press('enter')
        print(f"Waiting for {target_chat_name} to process...")
        time.sleep(10) # Wait for response generation

        # 3. Switch back to Chrome and reload
        print("Switching back to Chrome...")
        if len(switch_keys_to_chrome) == 2: # Simple Alt+Tab
             pyautogui.hotkey(switch_keys_to_chrome[0], switch_keys_to_chrome[1])
        elif len(switch_keys_to_chrome) == 3: # Alt+Tab+Tab (Shouldn't happen with new logic, but kept for safety)
             pyautogui.keyDown(switch_keys_to_chrome[0])
             time.sleep(3)
             pyautogui.press(switch_keys_to_chrome[1])
             time.sleep(3)
             pyautogui.press(switch_keys_to_chrome[2])
             time.sleep(3)
             pyautogui.keyUp(switch_keys_to_chrome[0])
        else:
             print(f"Error: Unsupported key sequence for switching back to chrome: {switch_keys_to_chrome}")
             raise Exception("Loop Error: Invalid window switch sequence back to Chrome.")
        time.sleep(3)

        print("Reloading Chrome page...")
        driver.get("http://localhost:3000/chat")
        time.sleep(5) # Wait for reload

        # 4. Toggle turn for next iteration
        current_turn_target = "chat1" if current_turn_target == "chat2" else "chat2"
        print(f"--- Loop Turn End --- Next target: {current_turn_target.upper()} ---")


except (TimeoutException, NoSuchElementException, ElementClickInterceptedException) as e:
    print(f"\n!!!!!!!!!!!!!! A Selenium error occurred !!!!!!!!!!!!!!")
    print(f"Error details: {e}")
    pyautogui.alert(f"A browser interaction error occurred:\n{e}", "Selenium Error")
except ValueError as e:
    print(f"\n!!!!!!!!!!!!!! A data error occurred !!!!!!!!!!!!!!")
    print(f"Error details: {e}")
    pyautogui.alert(f"A data error occurred (e.g., empty scraped text):\n{e}", "Data Error")
except Exception as e:
    import traceback
    print(f"\n!!!!!!!!!!!!!! An unexpected error occurred !!!!!!!!!!!!!!")
    print(f"Error type: {type(e).__name__}")
    print(f"Error details: {e}")
    print("Traceback:")
    traceback.print_exc() # Print full traceback for debugging
    pyautogui.alert(f"An unexpected error occurred:\n{type(e).__name__}: {e}", "Error")
    # Keep browser open

# --- Final Message ---
print("\nScript execution stopped (due to error or manual interruption). Browser remains open.")
# Keep the driver alive until manually closed or script terminated
# To automatically close on error, move driver.quit() into the except blocks if desired.
while True: # Keep script alive to keep browser open
    try:
        # Check if browser window is still open, exit if not
        driver.current_window_handle
        time.sleep(5)
    except:
        print("Browser window closed. Exiting script.")
        break
# driver.quit() # Explicitly close driver if needed at the very end
