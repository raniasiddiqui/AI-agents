import asyncio
import re
from groq import Groq
from playwright.async_api import async_playwright
from urllib.parse import urlparse
from collections import deque
import subprocess
import json
import google.generativeai as genai
import os
from crewai import Agent
import requests


OPENROUTER_API_KEY = "YOUR_OPENROUTER_API_KEY_HERE"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

# Configure Groq API

GROQ_API_KEY = "YOUR_GROQ_API_KEY"
groq_client = Groq(api_key=GROQ_API_KEY)

class GroqOSSAgent:
    """Base agent class using Groq models"""
    def __init__(self, name: str, system_message: str, model_name: str):
        self.name = name
        self.system_message = system_message
        self.model_name = model_name

    async def generate_response(self, message: str) -> str:
        try:
            def run_completion():
                completion = groq_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self.system_message},
                        {"role": "user", "content": message}
                    ]
                )
                return completion.choices[0].message.content

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, run_completion)
        except Exception as e:
            return f"Error generating Groq OSS response: {str(e)}"
        
class OpenRouterAgent:
    """Base agent class using OpenRouter models"""
    def __init__(self, name: str, system_message: str, model_name: str):
        self.name = name
        self.system_message = system_message
        self.model_name = model_name

    async def generate_response(self, message: str) -> str:
        try:
            def run_completion():
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": self.system_message},
                        {"role": "user", "content": message}
                    ]
                }
                response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload)
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, run_completion)
        except Exception as e:
            return f"Error generating OpenRouter response: {str(e)}"

async def refine_instruction(instruction: str) -> str:
    refiner = OpenRouterAgent(
        name="InstructionRefiner",
        system_message="""
        You are an expert in writing clear, precise, and unambiguous instructions for QA automation tasks.
        Your task is to refine the provided instruction and make it understandable by an LLM easily, to ensure it is:
        - Clear and concise, actionable language, avoiding ambiguity.
        - Unambiguous with no vague terms
        - Structured for easy interpretation by automation agents
        - Focused on specifying exact actions, selectors, and validations
        - Compliant with Playwright sync API requirements
        - Includes self-healing locator guidelines
        - Avoids placeholders or vague instructions
        - Follow Playwright sync API conventions
        - Include possible self-healing locator strategies. These include ID, name, class name, tag name, CSS selector, XPath, and role-based selectors, and text-based selectors. They should be prioritized based on reliability and stability.
        - Focus on:
          - Setup steps (navigate, prepare data)
          - Action steps (click, fill, submit)
          - Verification steps (assertions, checks)
          - Error handling considerations        
        - Requests per-step pass/fail logging and assertions
        Output only the refined instruction as plain text, no markdown or explanations. Dont output any testcases in this step.
        """,
        model_name="deepseek/deepseek-r1-distill-llama-70b"
    )
    return await refiner.generate_response(instruction)

class SiteInspectorAgent(OpenRouterAgent):
    def __init__(self):
        system_message = """
        You are a site inspector that analyzes crawled web pages to extract reliable Playwright locators and discover QA-relevant insights for comprehensive test case generation.
        You receive snippets from multiple crawled pages of the site and the user's instruction describing specific functionalities.
        Analyze the crawled page snippets and user instruction to:
        - Summarize the site structure, key pages, navigation flows, and discovered features (e.g., forms, buttons, interactive elements, user journeys).
        - Identify possible test scenarios based on the site's elements and the user's instruction, including core functionalities, alternative flows, edge cases, and error conditions.
        - Extract and recommend reliable Playwright locators (ID, name, class name, tag name, CSS selector, XPath, role-based, text-based) for key elements mentioned in the instruction or discovered during crawling.
        - Suggest self-healing locator strategies and waits for dynamic content, prioritizing reliability and stability.
        - Provide insights to generate a wider range of test cases, such as alternative paths, error-prone areas, and integration points.
        Output a string starting with 'Site Insights and Recommended Locators: ' followed by a structured summary:
        - Site Structure: Summarize key pages, navigation patterns, and features.
        - Discovered Test Scenarios: List potential test cases (e.g., functional, negative, edge cases) based on crawled data and instruction.
        - Recommended Locators: List reliable locators for key elements, prioritized by stability (e.g., ID > role-based > text-based > CSS/XPath).
        If no URL was crawled, generate generic but reliable locators and insights based on common web patterns and the user's instruction.
        Ensure locators are:
        - Reliable and stable
        - Adaptable to dynamic content
        - Use self-healing strategies where possible
        - Include ID, name, class name, tag name, CSS selector, XPath, and role-based selectors
        - Use text-based selectors where applicable
        - Prioritize selectors based on reliability and stability
        """
        super().__init__("SiteInspector", system_message, model_name="deepseek/deepseek-r1-distill-llama-70b")

    async def crawl_site(self, start_url: str, username: str, password: str, max_pages: int = 5) -> dict:
        """Simple BFS crawler to fetch up to max_pages internal pages and their HTML snippets after logging in."""
        from collections import deque
        visited = set()
        to_visit = deque([start_url])
        page_contents = {}
        base_origin = urlparse(start_url).scheme + "://" + urlparse(start_url).netloc

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()
            try:
                # Navigate to login page
                print(f"Navigating to {start_url}...")
                await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)

                # Check if a "Sign In" button/link needs to be clicked
                sign_in_button = await page.query_selector("a[href*='login'], button:has-text('Sign In'), button:has-text('Log In')")
                if sign_in_button:
                    print("Clicking 'Sign In' button...")
                    await sign_in_button.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=30000)

                # Selectors for email, password, and submit button. These can be expanded based on common patterns.
                email_selectors = [
                    "#userNameInput",
                    "[data-testid='email']",
                    "input[type='email']",
                    "input[name='email']",
                    "input[id='email']",
                    "//input[contains(@placeholder, 'Email')]"

                ]
                password_selectors = [
                    "#passwordInput",
                    "[data-testid='password']",
                    "input[type='password']",
                    "input[name='password']",
                    "input[id='password']",
                    "//input[contains(@placeholder, 'Password')]"
                ]
                submit_selectors = [
                   "#submitButton", 
                     "[data-testid='submit']",
                    ".submit",
                    "[role='button']:has-text('Sign in')",
                    "button[type='submit']",
                    "button:has-text('Sign In')",
                    "button:has-text('Log In')"
                ]

                email_locator = None
                for selector in email_selectors:
                    try:
                        await page.wait_for_selector(selector, state="visible", timeout=10000)
                        email_locator = selector
                        break
                    except:
                        continue

                if not email_locator:
                    html = await page.content()
                    print(f"Error: No email input found. Page HTML:\n{html[:1000]}...")
                    raise Exception("No email input found with provided selectors")

                print(f"Filling email with selector: {email_locator}")
                await page.fill(email_locator, username)
                await page.wait_for_timeout(1000) 

                password_locator = None
                for selector in password_selectors:
                    try:
                        await page.wait_for_selector(selector, state="visible", timeout=10000)
                        password_locator = selector
                        break
                    except:
                        continue

                if not password_locator:
                    raise Exception("No password input found with provided selectors")

                print(f"Filling password with selector: {password_locator}")
                await page.fill(password_locator, password)
                await page.wait_for_timeout(1000)

                submit_locator = None
                for selector in submit_selectors:
                    try:
                        await page.wait_for_selector(selector, state="visible", timeout=10000)
                        submit_locator = selector
                        break
                    except:
                        continue

                if not submit_locator:
                    raise Exception("No submit button found with provided selectors")

                print(f"Clicking submit with selector: {submit_locator}")
                await page.click(submit_locator)

                # Wait for post-login page, checking for either Home Screen or error
                try:
                    # Wait for a search panel or home screen indicator
                    await page.wait_for_selector(".search-panel, #searchPanel, [role='search']", state="visible", timeout=30000)
                    print(f"Logged in successfully at {start_url}")
                except:
                    # Check for login error message
                    error_selector = "text='Invalid credentials', text='Login failed', [role='alert']"
                    error_element = await page.query_selector(error_selector)
                    if error_element:
                        error_text = await error_element.inner_text()
                        print(f"Login failed with error: {error_text}")
                        raise Exception(f"Login failed: {error_text}")
                    # If no error message, try waiting for URL change or page content
                    await page.wait_for_timeout(5000)  # Brief pause for redirect
                    current_url = page.url
                    if current_url == start_url:
                        html = await page.content()
                        print(f"Error: No redirect after login. Current URL: {current_url}\nPage HTML:\n{html[:1000]}...")
                        raise Exception("No redirect after login attempt")
                    print(f"Redirected to {current_url} after login")

                # Start crawling after login
                while to_visit and len(page_contents) < max_pages:
                    current = to_visit.popleft()
                    if current in visited:
                        continue
                    visited.add(current)
                    try:
                        print(f"Crawling page: {current}")
                        await page.goto(current, wait_until="domcontentloaded", timeout=60000)
                        html = await page.content()
                        page_contents[current] = html[:4000]  # Snippet to avoid token limits
                        # Extract new internal links
                        new_links = await page.evaluate('''
                            () => {
                                return Array.from(document.querySelectorAll('a[href]'))
                                    .map(a => {
                                        let href = a.getAttribute('href');
                                        if (href) {
                                            try {
                                                let fullUrl = new URL(href, window.location.href).href;
                                                if (fullUrl.startsWith(%s)) {
                                                    return fullUrl;
                                                }
                                            } catch (e) {}
                                        }
                                        return null;
                                    })
                                    .filter(Boolean);
                            }
                        ''' % repr(base_origin))
                        for link in new_links:
                            parsed = urlparse(link)
                            if (link not in visited and
                                link not in to_visit and
                                not any(link.lower().endswith(ext) for ext in ('.pdf', '.jpg', '.png', '.gif', '.css', '.js', '.zip')) and
                                parsed.path != '/' and parsed.path != ''):
                                to_visit.append(link)
                    except Exception as e:
                        print(f"Error crawling {current}: {e}")
                        continue
            except Exception as e:
                print(f"Error during login or crawling: {e}")
                if not page_contents:
                    html = await page.content()
                    print(f"Page HTML on failure:\n{html[:1000]}...")
            finally:
                await context.close()
                await browser.close()
        return page_contents

    async def inspect_site(self, url: str, key_elements: str, instruction: str, username: str, password: str) -> str:
        if url:
            page_contents = await self.crawl_site(url, username, password, max_pages=5)
            if not page_contents:
                print("No pages crawled successfully.")
                return await self.generate_response(
                    f"No URL content crawled. Generate reliable Playwright locators and insights for {key_elements} based on common web patterns and the instruction: {instruction}"
                )
            content_str = "\n\n---\n\n".join([f"Page: {k}\nHTML Snippet:\n{v}" for k, v in page_contents.items()])
            crawl_summary = await self.generate_response(
                f"Start URL: {url}\nKey Elements to Focus: {key_elements}\nUser Instruction: {instruction}\nCrawled Pages Snippets:\n{content_str}"
            )
            recommendations = await self.generate_response(
                f"Analyze the crawl summary for site insights and locators: {crawl_summary}\nUser Key Elements: {key_elements}\nUser Instruction: {instruction}"
            )
            return recommendations
        else:
            return await self.generate_response(
                f"No URL provided. Generate reliable Playwright locators, self-healing strategies, and generic site insights (e.g., common flows for {key_elements}) based on common web patterns and the instruction: {instruction}"
            )

class PlannerAgentOSS(OpenRouterAgent):
    def __init__(self):
        system_message = """
        You are an expert QA test planner with deep NLP understanding.
        Your goal is to generate comprehensive test cases covering all possible variations, including but not limited to:

        Firstly, your priority is to generate test cases for the core functionalities described in the instruction, including insights from crawled site data.
        The core functionalities include covering complete flows for each feature mentioned in the instruction and discovered during site crawling.
        The features are the basic flow, alternative flow, pre-conditions, post-conditions, validations/rules mentioned in the instruction, and additional scenarios from crawled data.
        Then, expand to cover edge cases, error handling, and less common scenarios.
        After completing the core functionalities, generate test cases for the following types:
        - Functional (positive scenarios where the system works as expected)
        - Negative (invalid inputs, error handling, failures)
        - Boundary (edge cases like min/max values, limits)
        - Performance (load times, responsiveness under stress; simulate with Playwright where possible, e.g., multiple interactions, timeouts)
        - Security (vulnerabilities like injection, authentication bypass; automate checks for common issues like XSS, CSRF if detectable via UI)
        - Integration (interactions between components, APIs if accessible via UI)
        - Usability (UI/UX checks like accessibility, responsiveness, user flows; use Playwright for visibility, focus, etc.)
        - Regression (re-testing core functionalities to ensure no breaks)
        - Smoke (basic functionality checks to verify build stability)
        - Sanity (quick checks on specific changes or fixes)
        - Database (if applicable, verify data persistence, queries via UI interactions)
        - End-to-End (full user journeys from start to finish)
        - Exploratory (suggest automated heuristics or random inputs for discovery; adapt to automation where feasible)

        Analyze the provided instruction, refined details, and site insights/locator recommendations to generate test cases for as many of these types as applicable. If a type doesn't apply, skip it but aim to cover all possible variations where relevant.
        Prioritize generating multiple test cases per type to cover variations (e.g., different inputs, scenarios).
        For each test case, include:
        - Test Case Name (Indicate type, e.g., Functional - Login Success)
        - Description (Functionality being tested, including all possible variations)
        - Preconditions (Setup required, e.g., browser state, data)
        - Test Case Details (High-level overview)
        - Step-by-step actions with clear selectors, actions, and validations (Use Playwright sync API, self-healing locators, waits, per-step logging/assertions)
        - Expected Result (Clear pass/fail criteria)

        Structure your response with sections for each test type (e.g., ## Functional Test Cases, ## Negative Test Cases, etc.).
        Under each section, provide a numbered list of test cases.
        Use precise language and avoid ambiguity.
        Focus on:
        - Setup steps (navigate, prepare data)
        - Action steps (click, fill, submit)
        - Verification steps (assertions, checks)
        - Error handling considerations
        - Use clear, actionable language
        - Output only the test cases, no explanations or markdown beyond the required section headers and numbered lists
        - Follow Playwright sync API conventions
        - Use self-healing locator strategies (e.g., ID, name, class name, tag name, CSS selector, XPath, role-based selectors, text-based selectors)
        - Prioritize selectors based on reliability and stability
        - Include self-healing locator strategies (e.g., role-based, text-based over IDs if dynamic)
        - Ensure each test case is executable with clear pass/fail criteria
        - Include per-step pass/fail logging and assertions (e.g., console.log('Step 1: Passed') or expect().toBeVisible())
        - Use the provided instruction, refined details, and locator recommendations/site insights as context for generating test cases
        - For performance/security/usability, adapt to Playwright capabilities (e.g., measure page load time, check for alerts, verify ARIA attributes)
        - For exploratory, generate test cases with randomized or varied inputs to simulate exploration
        - Generate only the test cases, no explanations or markdown beyond the required section headers and numbered lists
        - Use the provided instruction, refined details, and locator recommendations as context for generating test cases
        - First generate testcases for core functionalities which mainly includes basic flow, alternate flow, pre-conditions, post-conditions, validations/rules mentioned in the instruction.
        - Then expand to cover all other types of testcases as mentioned above.
        """
        super().__init__("PlannerOSS", system_message, model_name="deepseek/deepseek-r1-distill-llama-70b")

class TestCodeGenerator(GroqOSSAgent):
    def __init__(self):
        system_message = """
        You are an expert in generating executable Python scripts for QA automation using Playwright sync API.
        Given a test case description with name, description, preconditions, details, steps, expected result, and using the locator recommendations from the context.
        Determine if it is possible to automate. If the test case requires manual intervention, special simulation like network throttling for performance, or interacting with the database, or something not easily done with Playwright UI automation, respond with 'Not Automatable'.
        If automatable, generate a complete standalone Python script that:
        - Imports from playwright.sync_api import sync_playwright, expect
        - Uses with sync_playwright() as p:
        - Launches browser = p.chromium.launch(headless=True)
        - Creates context = browser.new_context()
        - Creates page = context.new_page()
        - Implements the preconditions and steps using the selectors from the context or recommended locators.
        - Use either the provided selectors or self-healing locator strategies (ID, name, class name, tag name, CSS selector, XPath, role-based selectors, text-based selectors) prioritized by reliability and stability
        - Uses page.goto, page.fill, page.click, page.wait_for_selector, etc.
        - For validations, use expect(page.locator(selector)).to_be_visible(), to_have_text(), etc.
        - If all assertions pass, print "Test Passed"
        - If any fails, catch exception and print "Test Failed: [reason]"
        - Include error handling with try-except.
        - Use the username and password from the prompt. If any test case requires login, include the login steps using the provided credentials.
        - Ensure the script is executable as a standalone file.
        - Use the url from the prompt.
        - Use self-healing locators as per guidelines.
        Output only the Python script as plain text if automatable, or 'Not Automatable'.
        """
        super().__init__("TestCodeGenerator", system_message, model_name="llama-3.3-70b-versatile")

class UserProxyAgent:
    def __init__(self, name: str):
        self.name = name

    async def initiate_chat(self, agent, message: str) -> str:
        return await agent.generate_response(message)
    
def parse_test_cases(test_cases_text: str):
    """
    Extracts structured test cases regardless of formatting.
    Matches blocks with Name, Description, Preconditions, Details, Steps, Expected Result.
    """
    pattern = re.compile(
        r"(?:###|##)?\s*(?:\d+\. )?(?P<name>[^\n]+)\n"
        r".*?(?:Description|Desc)\*?\*?:\s*(?P<description>.*?)\n"
        r".*?(?:Preconditions|Pre-Conditions)\*?\*?:\s*(?P<preconditions>.*?)\n"
        r".*?(?:Test Case Details|Details)\*?\*?:\s*(?P<details>.*?)\n"
        r".*?(?:Steps?|Step-by-step)\*?\*?:\s*(?P<steps>.*?)\n"
        r".*?(?:Expected Result|Expected)\*?\*?:\s*(?P<expected>.*?)(?=\n###|\n##|$)",
        re.DOTALL | re.IGNORECASE
    )

    test_cases_list = []
    for match in pattern.finditer(test_cases_text):
        test_cases_list.append({
            'name': match.group("name").strip(),
            'description': match.group("description").strip(),
            'preconditions': match.group("preconditions").strip(),
            'details': match.group("details").strip(),
            'steps': match.group("steps").strip(),
            'expected': match.group("expected").strip()
        })

    return test_cases_list 

def clean_generated_code(code: str) -> str:
    """
    Cleans up generated code by removing markdown fences, 
    commentary, and stray LLM text that breaks execution.
    """
    # Remove markdown fences
    code = re.sub(r"```[a-zA-Z]*", "", code)

    # Remove narrative lines (non-code)
    cleaned_lines = []
    for line in code.splitlines():
        if re.match(r"^\s*(#|from |import |with |def |class |try|except|page\.|browser|context|print|expect)", line):
            cleaned_lines.append(line)
        elif line.strip().startswith(("Test Case", "<think>", "###", "Alright")):
            continue
        elif line.strip() == "":
            continue
        else:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()

async def main():
    os.environ["GOOGLE_API_KEY"] = "AIzaSyDiAIKIHxFx_DPLKLViLamimYO-2gE36nU"
    print("🤖 Initializing Multi-Agent QA Planning System...\n")

    user = UserProxyAgent("User")
    inspector = SiteInspectorAgent()
    planner = PlannerAgentOSS()

    # Accept any prompt from user
    user_prompt = input("Enter your automation instruction:\n").strip()

    # Auto-detect site URL from prompt (basic regex match for http/https links)
    url_match = re.search(r'(https?://[^\s]+)', user_prompt)
    site_url = url_match.group(1) if url_match else None

    # Extract username and password from prompt
    # Extract username and password from prompt
    username_match = re.search(r"username\s*=\s*'([^']+)'", user_prompt)
    password_match = re.search(r"password\s*=\s*'([^']+)'", user_prompt)
    username = username_match.group(1) if username_match else None
    password = password_match.group(1) if password_match else None


    element_keywords = []
    for kw in ["search", "input", "button", "title", "heading", "section", "link", "locator", "element", "screenshot", "scroll", "verify", "assert", "check", "capture", "wait", "load", "click", "fill", "submit", "navigate", "page", "url", "text", "content", "selector", "xpath", "css", "id", "name", "class", "tag", "role", "exact", "visible", "hidden", "exists", "not exists", "error", "fail", "pass", "retry", "timeout", "sleep", "wait_for", "print", "output", "log", "debug", "info", "warn", "assertion", "asserts", "check", "checks", "validation", "validations", "test", "tests", "step", "steps", "action", "actions", 
               "interaction", "interactions", "element interaction", "element interactions", "locator strategy", "self-healing", "self healing", "dynamic", "dynamic elements", "dynamic content", "dynamic locators", "dynamic selectors", "dynamic elements strategy", "dynamic content strategy", "dynamic locators strategy", "dynamic selectors strategy"]:
        if kw in user_prompt.lower():
            element_keywords.append(kw)
    key_elements = ", ".join(element_keywords) if element_keywords else "main interactive elements"

    # Step 0: Refining user instruction
    print("Step 0: Refining user instruction...")
    refined_instruction = await refine_instruction(user_prompt)
    print("Refined Instruction:\n", refined_instruction)
    print("=" * 50)

    # Step 0.5: Inspecting site for locators and insights
    print("Step 0.5: Inspecting site for locators and insights...")
    locator_recommendations = await inspector.inspect_site(site_url, key_elements, user_prompt, username, password)
    refined_instruction += f"\n{locator_recommendations}"
    print("Site Insights and Locator Recommendations:\n", locator_recommendations)
    print("=" * 50)

    # Step 1: Planning test cases
    print("Step 1: Planning test cases...")
    test_cases_text = await user.initiate_chat(planner, refined_instruction)
    print(test_cases_text)
    print("=" * 50)

    # Step 2: Generate and execute automatable test cases
    print("Step 2: Generating and executing automatable test cases...")

    
    # Parse the test_cases string
    pattern = re.compile(
    r'(?:(?:###\s*\d+\.\s*)?(.*?)\n)?'
    r'(?:\*\*Description\*\*:\s*(.*?)\n)?'
    r'(?:\*\*Preconditions\*\*:\s*(.*?)\n)?'
    r'(?:\*\*Test Case Details\*\*:\s*(.*?)\n)?'
    r'(?:\*\*Steps\*\*:\s*(.*?))?'
    r'(?:\*\*Expected Result\*\*:\s*(.*?))?(?=\n###|\n##|$)',
    re.DOTALL | re.MULTILINE
)

    test_cases_list = []
    for match in pattern.finditer(test_cases_text):
        if not any(match.groups()):  # skip empty matches
            continue
        name = (match.group(1) or "").strip()
        desc = (match.group(2) or "").strip()
        pre = (match.group(3) or "").strip()
        details = (match.group(4) or "").strip()
        steps = (match.group(5) or "").strip()
        expected = (match.group(6) or "").strip()
        test_cases_list.append({
        'name': name,
        'description': desc,
        'preconditions': pre,
        'details': details,
        'steps': steps,
        'expected': expected
        })

# Save parsed test cases to JSON for reuse
    with open("test_cases.json", "w", encoding="utf-8") as f:
        json.dump(test_cases_list, f, indent=2, ensure_ascii=False)

    print(f"Extracted {len(test_cases_list)} test cases. Saved to test_cases.json")

    generator = TestCodeGenerator()
    combined_file = "generated_test_cases.py"
    for idx, tc in enumerate(test_cases_list):
        message = (
        f"Test Case: {tc['name']}\n"
        f"Description: {tc['description']}\n"
        f"Preconditions: {tc['preconditions']}\n"
        f"Details: {tc['details']}\n"
        f"Steps: {tc['steps']}\n"
        f"Expected: {tc['expected']}\n"
        f"Context: {refined_instruction} {user_prompt}"
    )
        code = await generator.generate_response(message)
        if "Not Automatable" in code:
            print(f"Test Case {idx+1}: {tc['name']} - Not Automatable")
            continue
        code = clean_generated_code(code)

        mode = 'w' if idx == 0 else 'a'
        with open(combined_file, mode, encoding='utf-8') as f:
            f.write(f"\n\n# ===== Test Case {idx+1}: {tc['name']} =====\n\n")
            f.write(code)

        # else:
        #     code = clean_generated_code(code)
        #     file_name = f"test_case_{idx+1}.py"
        #     with open(file_name, 'w', encoding='utf-8') as f:
        #         f.write(code)
        #     print(f"Generated script for {tc['name']} in {file_name}")
        # # Execute the script
        #     result = subprocess.run(["python", file_name], capture_output=True, text=True)
        #     output = result.stdout.strip()
        #     error = result.stderr.strip()
        #     if result.returncode == 0 and "Test Passed" in output:
        #         print(f"Test Case {idx+1}: {tc['name']} - Passed")
        #     else:
        #         print(f"Test Case {idx+1}: {tc['name']} - Failed")
        #         if error:
        #             print(f"Error: {error}")
        #         if output:
        #             print(f"Output: {output}")

        print("\nTest case generation complete!")

if __name__ == "__main__":
    asyncio.run(main())