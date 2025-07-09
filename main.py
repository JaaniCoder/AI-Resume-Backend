from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import os
import requests
import re
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import inch

load_dotenv()

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Simple AI Resume Builder",
        "endpoints": {
            "/generate": "POST - Generate resume text",
            "/generate-pdf": "POST - Generate and download PDF resume"
        }
    })

def create_resume_prompt(data):
    """Generate structured resume prompt"""
    return f"""
You are a professional resume writer. Create a resume using the provided information. 

IMPORTANT: Start directly with the person's name. Do NOT include any introductory text like "Here is the formatted resume" or any explanations.

Use this EXACT format:

{data.get('name', '')}
[Job Title/Profession based on experience]
{data.get('phone', '')} | {data.get('email', '')}

PROFILE
[Write a compelling 2-3 line professional summary based on: {data.get('summary', '')}]

EMPLOYMENT HISTORY
[Format each job as: Job Title | Company Name | Date Range]
[Add 3-4 bullet points for each role based on: {data.get('experience', '')}]

EDUCATION
[Format as: Degree | Institution | Date Range based on: {data.get('education', '')}]

SKILLS
[Organize skills into categories like: Programming Languages: [list], Frameworks: [list] based on: {data.get('skills', '')}]

Remember: Start immediately with the name, no introductory text whatsoever.
"""

def generate_resume_text(data):
    """Generate resume text using Groq API"""
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a professional resume writer. Create well-formatted, ATS-optimized resumes."},
                {"role": "user", "content": create_resume_prompt(data)}
            ],
            "temperature": 0.3,
            "max_tokens": 1500
        }

        response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload)
        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"].strip()
            
            # Remove any unwanted AI-generated intro/outro text
            content = re.sub(r'^(Here is|Here\'s).*?resume:?\s*', '', content, flags=re.IGNORECASE)
            content = re.sub(r'^.*formatted resume.*?:\s*', '', content, flags=re.IGNORECASE)
            content = re.sub(r'I hope this helps.*$', '', content, flags=re.IGNORECASE)
            content = re.sub(r'^.*?based on.*?:\s*', '', content, flags=re.IGNORECASE)
            
            return content.strip()
    except Exception as e:
        print(f"Error generating resume: {e}")
        return None

def create_pdf_resume(resume_text, filename="resume.pdf"):
    """Create PDF with modern, professional styling"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)

    styles = getSampleStyleSheet()

    # Custom Styles
    name_style = ParagraphStyle('Name', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER, spaceAfter=6)
    title_style = ParagraphStyle('Title', parent=styles['Normal'], fontSize=12, alignment=TA_CENTER, spaceAfter=6)
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, textColor=colors.HexColor("#555555"), spaceAfter=16)

    section_title_style = ParagraphStyle('SectionTitle', fontSize=11, fontName='Helvetica-Bold', alignment=TA_LEFT,
                                         backColor=colors.HexColor('#E5E8E8'), textColor=colors.HexColor('#2C3E50'),
                                         spaceBefore=12, spaceAfter=6, leftIndent=0, leading=14)

    body_style = ParagraphStyle('Body', fontSize=10, fontName='Helvetica', alignment=TA_LEFT, leading=14)
    bullet_style = ParagraphStyle('Bullet', fontSize=10, fontName='Helvetica', leftIndent=14, spaceBefore=2, leading=12)
    date_style = ParagraphStyle('Date', fontSize=10, alignment=TA_RIGHT, textColor=colors.HexColor('#7F8C8D'))
    skill_style = ParagraphStyle('Skill', fontSize=10, fontName='Helvetica', alignment=TA_LEFT, leading=12)

    story = []
    lines = [line.strip() for line in resume_text.split('\n') if line.strip()]
    i = 0

    # Header section
    if i < len(lines):
        story.append(Paragraph(lines[i], name_style))  # Name
        i += 1
    if i < len(lines):
        story.append(Paragraph(lines[i], title_style))  # Title
        i += 1
    if i < len(lines):
        story.append(Paragraph(lines[i], contact_style))  # Contact Info
        i += 1

    current_section = ""

    while i < len(lines):
        line = lines[i]
        # Detect section headers
        if line.upper() in ["PROFILE", "EMPLOYMENT HISTORY", "EDUCATION", "SKILLS", "INTERNSHIPS", "REFERENCES"]:
            current_section = line.upper()
            story.append(Paragraph(current_section, section_title_style))
            i += 1
            continue

        if current_section in ["EMPLOYMENT HISTORY", "EDUCATION", "INTERNSHIPS"] and '|' in line:
            parts = [p.strip() for p in line.split('|')]
            left = parts[0]
            right = ' | '.join(parts[1:])
            row = [[Paragraph(left, body_style), Paragraph(right, date_style)]]
            table = Table(row, colWidths=[300, 180])
            table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            story.append(table)
        elif line.startswith('•') or line.startswith('-'):
            bullet = line.lstrip('•- ').strip()
            story.append(Paragraph(f"• {bullet}", bullet_style))
        elif current_section == "SKILLS" and ':' in line:
            cat, skills = line.split(':', 1)
            row = [[Paragraph(f"{cat.strip()}:", body_style), Paragraph(skills.strip(), skill_style)]]
            table = Table(row, colWidths=[150, 330])
            table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            story.append(table)
        else:
            story.append(Paragraph(line, body_style))

        i += 1

    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route("/generate", methods=["POST"])
def generate_resume():
    """Generate resume text only"""
    try:
        data = request.get_json()
        
        if not data or not data.get('name') or not data.get('email'):
            return jsonify({"error": "Name and email are required"}), 400
        
        resume_text = generate_resume_text(data)
        
        if resume_text:
            return jsonify({"resume": resume_text, "success": True})
        else:
            return jsonify({"error": "Failed to generate resume"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/generate-pdf", methods=["POST"])
def generate_pdf_resume():
    """Generate resume and return PDF file"""
    try:
        data = request.get_json()
        
        if not data or not data.get('name') or not data.get('email'):
            return jsonify({"error": "Name and email are required"}), 400
        
        resume_text = generate_resume_text(data)
        if not resume_text:
            return jsonify({"error": "Failed to generate resume"}), 500
        
        pdf_buffer = create_pdf_resume(resume_text)
        filename = f"{data.get('name', 'resume').replace(' ', '_')}_resume.pdf"
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test", methods=["GET"])
def test_api():
    """Test Groq API connection"""
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": "Say hello!"}],
            "temperature": 0.3,
            "max_tokens": 50
        }

        response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload)
        
        if response.status_code == 200:
            return jsonify({"status": "API connection successful!", "model": GROQ_MODEL})
        else:
            return jsonify({"error": "API connection failed"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    if not GROQ_API_KEY:
        print("Warning: GROQ_API_KEY not found!")
    
    print("Starting Simple AI Resume Builder...")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
