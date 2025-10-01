## 🤖 Multi-Agent QA Automation System with Groq & Playwright

This project implements a multi-agent QA automation system powered by Groq open-source models and Playwright. It refines natural language QA instructions, inspects websites to generate stable Playwright locators, and plans comprehensive test cases across multiple categories (functional, negative, performance, security, exploratory, etc.).

### ✨ Key Features

1. 🧠 Instruction Refinement – Converts QA instructions into clear, structured, and Playwright-ready automation steps.
   These instructions are generated from the "Feature_Description_through_Documents.ipynb" file.
2. 📄 The file "Feature_Description_through_Documents.ipynb" takes any functional specification document in a pdf format, and generates exact description of any feature in detail from the document. This saves the manual effort of going into the files and finding out description for each of the feature. This description is passed to the instruction refiner to refine it more. 

3. 🔍 Site Inspector Agent – Analyzes webpages and generates robust self-healing locators (ID, name, class, CSS, XPath, role-based, text-based).

4. Crawl Website - This crawls any website & generates reccomended locators & selectors that can be passed to the planner agent.

5. 📋 Test Planner Agent – Creates test cases covering:

      - Functional

      - Negative & Boundary

      - Performance & Security
      
      - Integration & Regression
      
      - Usability & Accessibility
      
      - End-to-End Journeys

6. 🔄 Self-Healing Locator Strategies – Ensures automation scripts adapt to DOM changes.

7. ⚡ Async Multi-Agent Orchestration – Agents collaborate to refine, inspect, and generate test cases automatically.

### 🏗️ Project Workflow

1. User Input: Provide a natural language QA instruction (e.g., "Test login with valid credentials and verify dashboard loads").

2. Instruction Refiner: Cleans and structures the instruction into precise Playwright-compatible steps.

3. Site Inspector:

    - If URL is provided → inspects the DOM, extracts locators. Refer to AI_testcases_with_URL.py file

    - If no URL → generates generic but reliable locator strategies. Refer to AI_testcases.py file.

4. Planner Agent: Generates detailed Playwright test cases across multiple testing categories.

✅ Output: A structured set of test cases with selectors, actions, and validations.
