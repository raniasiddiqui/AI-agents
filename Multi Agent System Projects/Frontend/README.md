This multi-agent system is designed to automate the process of generating and executing QA test cases for web applications. It takes a user-provided instruction (e.g., a description of a functionality to test- this is generated from the FSD), optionally including a website URL, username, and password, and produces executable Playwright test scripts. The system uses a modular, agent-based architecture where each agent handles a specific task in the QA automation pipeline. The agents communicate asynchronously, leveraging APIs like Groq and OpenRouter for natural language processing and Playwright for web automation.

The flow of the system is as followings:
- FSD Prompt Learning: A list of features are passed to the FSD, and then description of detailed features is generated from the FSD. This description, which is the requirement to be tested, is then passed as a prompt to the user input.
- User Input Processing: Accepts a user instruction, extracts key elements (e.g., URL, credentials, keywords), and refines it for clarity.
- Agents: Specialized classes that handle specific tasks such as instruction refinement that refines the user instruction, site inspection that crawls and learns the feature to be tested, test case planning, and code generation of the generated test cases.
- Workflow: A sequential process that refines the instruction, crawls the target website (if provided), generates test cases, and produces executable Python scripts.
- Output: A set of test cases saved as JSON and executable Python scripts for Playwright automation.
Playwright Codegen: This records the interactions through the website & stores locators in a script
- Prompt Refiner: Finally in the last step, we give the executable python scripts that were generated previously by the coder, along with the playwright codegen locator recommendations to generate a refiner cleaner script that we automatically run. 
- Executed Test script: A final script is then produced by the prompt refiner, which is ready to run.

Note: I am in process of refining the entire QA workflow, from gathering requirements, to generating FSD OR BRDs, to generating testcases, and executing them, to finding bugs. This repository is in continious development, as i make further progress.

