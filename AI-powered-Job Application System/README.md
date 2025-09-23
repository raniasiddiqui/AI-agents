🚀 Job Application Optimization System 

An AI-powered Streamlit application that helps job seekers optimize their resumes and prepare for interviews by analyzing job descriptions and tailoring applications accordingly.

***✨ Features***

🤖 AI-Powered Analysis

- Job Requirements Analyst: Extracts and categorizes key requirements, skills, and qualifications
- Skills Matcher: Identifies matching skills, gaps, and areas to emphasize
- Resume Tailorer: Rewrites your resume with job-specific keywords and optimization
- Interview Coach: Creates personalized interview questions and talking points

📋 Flexible Input Methods

- PDF Upload: Extract text directly from PDF files
- Text Input: Copy and paste job descriptions and resumes
- Real-time Preview: See extracted content before processing

📊 Comprehensive Output

- Job Analysis: Structured breakdown of must-have vs. nice-to-have skills
- Skills Matching: Detailed gap analysis and recommendations
- Optimized Resume: ATS-friendly, keyword-rich resume tailored to the job
- Interview Preparation: Custom questions, answers, and talking points

***🛠️ Installation***

Prerequisites

- Python 3.8 or higher
- Google Gemini API key

1. Clone the Repository
- git clone https://github.com/yourusername/job-application-optimizer.git
- cd job-application-optimizer
2. Install Dependencies
- pip install -r requirements.txt
Or install individually:
- pip install streamlit PyPDF2 crewai langchain-google-genai google-generativeai
3. Get Your Google Gemini API Key

- Visit Google AI Studio
- Create a new API key
- Keep it secure - you'll enter it in the app

🚀 Usage
1. Start the Application
- streamlit run app.py
