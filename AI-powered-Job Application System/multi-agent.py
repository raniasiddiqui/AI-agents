import os
import streamlit as st
import PyPDF2
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
from google.generativeai import configure
import google.generativeai as genai
from crewai import LLM
import io
import time

# Configure page
st.set_page_config(
    page_title="Job Application Optimizer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure Gemini API key
@st.cache_resource
def configure_llm(api_key):
    """Configure the LLM with the provided API key"""
    try:
        return LLM(
            model="gemini/gemini-2.0-flash",
            api_key=api_key
        )
    except Exception as e:
        st.error(f"Error configuring LLM: {e}")
        return None

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file) -> str:
    """Extract text from uploaded PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return ""

# Initialize agents (will be created after API key is provided)
def create_agents(llm):
    """Create all the agents with the configured LLM"""
    job_analyst = Agent(
        role="Job Requirements Analyst",
        goal="Extract and categorize key requirements, skills, responsibilities, and qualifications from a job description.",
        backstory="You are an expert recruiter skilled at dissecting job postings to identify critical hiring criteria.",
        llm=llm,
        verbose=True
    )

    skills_matcher = Agent(
        role="Skills and Experience Matcher",
        goal="Compare the user's resume with job requirements to identify matches, gaps, and areas to emphasize.",
        backstory="You are a career coach adept at aligning candidate profiles with job demands.",
        llm=llm,
        verbose=True
    )

    resume_tailorer = Agent(
        role="Resume Tailorer and Rewriter",
        goal="Rewrite the resume to highlight relevant skills and experiences using job-specific keywords.",
        backstory="You are a professional resume writer optimizing resumes for ATS and human recruiters.",
        llm=llm,
        verbose=True
    )

    interview_coach = Agent(
        role="Interview Preparation Coach",
        goal="Create tailored talking points, sample interview questions, and answers based on the job and resume.",
        backstory="You are an interview strategist who prepares candidates to confidently showcase their value.",
        llm=llm,
        verbose=True
    )
    
    return job_analyst, skills_matcher, resume_tailorer, interview_coach

def create_tasks(agents):
    """Create all tasks with the provided agents"""
    job_analyst, skills_matcher, resume_tailorer, interview_coach = agents
    
    analyzer_task = Task(
        description="Analyze the provided job description: {job_description}. Output a structured summary in markdown format listing must-have skills, nice-to-have skills, key responsibilities, and required qualifications.",
        expected_output="A markdown report with sections for must-haves, nice-to-haves, responsibilities, and qualifications.",
        agent=job_analyst
    )

    skills_task = Task(
        description="Using the job analysis and the user's resume: {resume}, identify matching skills/experiences, gaps, and areas to highlight for the job.",
        expected_output="A markdown report detailing matches, gaps, and recommendations for resume adjustments.",
        agent=skills_matcher,
        context=[analyzer_task]
    )

    resume_task = Task(
        description="Rewrite the resume based on the skills matching report and job analysis, emphasizing relevant areas and using job-specific language.",
        expected_output="A rewritten resume in markdown format, optimized for the job.",
        agent=resume_tailorer,
        context=[analyzer_task, skills_task]
    )

    interview_task = Task(
        description="Using the tailored resume, job analysis, and skills match, generate interview talking points, 5 potential questions with sample answers, and preparation tips.",
        expected_output="A markdown interview preparation guide with talking points, questions/answers, and tips.",
        agent=interview_coach,
        context=[analyzer_task, skills_task, resume_task]
    )
    
    return analyzer_task, skills_task, resume_task, interview_task

# Function to run the system
def run_career_agent(job_description: str, resume: str, llm):
    """Run the career optimization system"""
    if not job_description or not resume:
        st.error("Job description or resume is empty. Please check your inputs.")
        return None
    
    try:
        # Create agents and tasks
        agents = create_agents(llm)
        tasks = create_tasks(agents)
        
        # Create the Crew
        career_crew = Crew(
            agents=list(agents),
            tasks=list(tasks),
            process=Process.sequential,
            verbose=True
        )
        
        # Run the system
        result = career_crew.kickoff(inputs={"job_description": job_description, "resume": resume})
        return result
    except Exception as e:
        st.error(f"Error running the agent system: {e}")
        return None

# Main Streamlit App
def main():
    st.title("🚀 Job Application Optimization System")
    st.markdown("Optimize your resume and prepare for interviews using AI-powered analysis!")
    
    # Sidebar for API key
    with st.sidebar:
        st.header("⚙️ Configuration")
        api_key = st.text_input(
            "Enter your Google API Key",
            type="password",
            help="Your Gemini API key is required to run the analysis"
        )
        
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
            llm = configure_llm(api_key)
            if llm:
                st.success("✅ API Key configured successfully!")
            else:
                st.error("❌ Failed to configure API Key")
                return
        else:
            st.warning("⚠️ Please enter your Google API Key to continue")
            st.stop()
    
    # Main content area
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("📋 Job Description")
        job_input_method = st.radio(
            "How would you like to provide the job description?",
            ["Upload PDF", "Paste Text"]
        )
        
        job_description = ""
        if job_input_method == "Upload PDF":
            job_pdf = st.file_uploader(
                "Upload Job Description PDF",
                type="pdf",
                help="Upload a PDF containing the job description"
            )
            if job_pdf:
                job_description = extract_text_from_pdf(job_pdf)
                if job_description:
                    st.success("✅ Job description extracted successfully!")
                    with st.expander("Preview extracted text"):
                        st.text_area("Job Description Text", job_description, height=200, disabled=True)
        else:
            job_description = st.text_area(
                "Paste Job Description",
                height=300,
                placeholder="Paste the job description here..."
            )
    
    with col2:
        st.header("📄 Resume")
        resume_input_method = st.radio(
            "How would you like to provide your resume?",
            ["Upload PDF", "Paste Text"]
        )
        
        resume = ""
        if resume_input_method == "Upload PDF":
            resume_pdf = st.file_uploader(
                "Upload Resume PDF",
                type="pdf",
                help="Upload your resume in PDF format"
            )
            if resume_pdf:
                resume = extract_text_from_pdf(resume_pdf)
                if resume:
                    st.success("✅ Resume extracted successfully!")
                    with st.expander("Preview extracted text"):
                        st.text_area("Resume Text", resume, height=200, disabled=True)
        else:
            resume = st.text_area(
                "Paste Resume Content",
                height=300,
                placeholder="Paste your resume content here..."
            )
    
    # Process button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Optimize Application", type="primary", use_container_width=True):
            if not job_description or not resume:
                st.error("Please provide both job description and resume!")
            else:
                # Show progress
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("🔍 Analyzing job description...")
                progress_bar.progress(25)
                time.sleep(1)
                
                status_text.text("🎯 Matching skills and experience...")
                progress_bar.progress(50)
                time.sleep(1)
                
                status_text.text("📝 Tailoring resume...")
                progress_bar.progress(75)
                time.sleep(1)
                
                status_text.text("💼 Preparing interview guide...")
                progress_bar.progress(100)
                
                # Run the analysis
                with st.spinner("Processing your application..."):
                    result = run_career_agent(job_description, resume, llm)
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                if result:
                    st.success("🎉 Analysis completed successfully!")
                    
                    # Parse the result to separate different sections
                    def parse_crew_output(result):
                        """Parse the crew output to extract individual task results"""
                        result_str = str(result)
                        
                        # Try to access individual task outputs if result has tasks_output attribute
                        if hasattr(result, 'tasks_output') and result.tasks_output:
                            task_outputs = {}
                            for i, task_output in enumerate(result.tasks_output):
                                if i == 0:  # Job Analysis
                                    task_outputs['job_analysis'] = str(task_output.raw)
                                elif i == 1:  # Skills Match
                                    task_outputs['skills_match'] = str(task_output.raw)
                                elif i == 2:  # Resume
                                    task_outputs['resume'] = str(task_output.raw)
                                elif i == 3:  # Interview Prep
                                    task_outputs['interview_prep'] = str(task_output.raw)
                            return task_outputs, result_str
                        else:
                            # Fallback: try to parse the combined output by looking for section markers
                            sections = {
                                'job_analysis': result_str,
                                'skills_match': result_str,
                                'resume': result_str,
                                'interview_prep': result_str
                            }
                            
                            # Try to split by common patterns
                            if "# Job Requirements Analysis" in result_str or "## Job Requirements Analysis" in result_str:
                                # Split by headers if they exist
                                parts = result_str.split('#')
                                for part in parts:
                                    if 'job' in part.lower() and 'analysis' in part.lower():
                                        sections['job_analysis'] = f"#{part}"
                                    elif 'skills' in part.lower() and 'match' in part.lower():
                                        sections['skills_match'] = f"#{part}"
                                    elif 'resume' in part.lower():
                                        sections['resume'] = f"#{part}"
                                    elif 'interview' in part.lower():
                                        sections['interview_prep'] = f"#{part}"
                            
                            return sections, result_str
                    
                    # Parse the results
                    parsed_sections, complete_result = parse_crew_output(result)
                    
                    # Display results in tabs
                    tab1, tab2, tab3, tab4 = st.tabs([
                        "📊 Job Analysis", 
                        "🔍 Skills Match", 
                        "📄 Optimized Resume", 
                        "💼 Interview Prep"
                    ])
                    
                    with tab1:
                        st.markdown("### Job Requirements Analysis")
                        if 'job_analysis' in parsed_sections:
                            st.markdown(parsed_sections['job_analysis'])
                        else:
                            st.info("Job analysis section not found in output. Showing complete result:")
                            st.markdown(complete_result)
                    
                    with tab2:
                        st.markdown("### Skills and Experience Matching")
                        if 'skills_match' in parsed_sections:
                            st.markdown(parsed_sections['skills_match'])
                        else:
                            st.info("Skills matching section not found in output. Showing complete result:")
                            st.markdown(complete_result)
                    
                    with tab3:
                        st.markdown("### Tailored Resume")
                        resume_content = parsed_sections.get('resume', complete_result)
                        st.markdown(resume_content)
                        
                        # Download button for resume
                        st.download_button(
                            label="📥 Download Optimized Resume",
                            data=resume_content,
                            file_name="optimized_resume.md",
                            mime="text/markdown"
                        )
                    
                    with tab4:
                        st.markdown("### Interview Preparation Guide")
                        if 'interview_prep' in parsed_sections:
                            st.markdown(parsed_sections['interview_prep'])
                        else:
                            st.info("Interview preparation section not found in output. Showing complete result:")
                            st.markdown(complete_result)
                    
                    # Download all results
                    st.markdown("---")
                    st.download_button(
                        label="📥 Download Complete Analysis",
                        data=complete_result,
                        file_name="career_optimization_report.md",
                        mime="text/markdown"
                    )
                else:
                    st.error("❌ Failed to process your application. Please try again.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            <p>Built with ❤️ using Streamlit and CrewAI</p>
            <p><small>Make sure to keep your API key secure and never share it publicly.</small></p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()