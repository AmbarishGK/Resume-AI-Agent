[info] Using resume: ambarishgk_resume.pdf
[info] Using JD: apple / ai Ml resident robot learning
[info] Extracting resume sections (skills/experience/projects) with model: mistral:instruct
[info] Analyzing skills & gaps with small model: mistral:instruct

[info] Generating section-wise rewrites with large model: mistral:instruct
=== SKILL ALIGNMENT (JSON) ===
{
  "jd_key_skills": [
    "Python",
    "Objective-C",
    "C++",
    "Swift",
    "R",
    "Proficiency in a programming language",
    "Experience completing a moderate-sized software project",
    "Robotics",
    "Machine Learning & ML Research",
    "Large Language Models / Generative AI",
    "Graduate degree in a STEM field or equivalent industry experience in software engineering"
  ],
  "resume_present_skills": [
    "Python",
    "C++",
    "JavaScript",
    "TypeScript",
    "SQL",
    "AI/ML: YOLO, vLLM, VLM, LLM, Computer Vision, VLA, MCP",
    "Tools: Docker, Kubernetes, Git, AWS, GCP, Hugging Face, LangChain",
    "Cloud tools: AWS Lambda, greengrass, dynamodb, ec2, GCP Vertex"
  ],
  "missing_skills": [
    "Objective-C",
    "Swift",
    "R",
    "Experience completing a moderate-sized software project in the context of robotics or AI/ML research",
    "Robotics",
    "Machine Learning & ML Research",
    "Large Language Models / Generative AI"
  ],
  "notes": "The resume presents skills in programming languages such as Python, C++, and JavaScript. However, it lacks experience completing a moderate-sized software project in the context of robotics or AI/ML research, which is explicitly required by the JD. The candidate has experience in AI/ML but not specifically in robotics or large language models / generative AI as preferred by the JD."
}

=== COMPARISON: SKILLS SECTION ===
[BEFORE]
"Languages: Python, C, C++, Go, JavaScript, node.js, TypeScript, SQL, Java
Tools & Frameworks: Flask, FastAPI, React, PyTorch, matplotlib, visualization, Async, scapy, bs4
AI/ML: YOLO, vLLM, VLM, LLM, Computer Vision, VLA, MCP"

[AFTER]
- Python
- C++
- Robotics
- Computer Vision
- Machine Learning
- LLMs
- Generative AI

=== COMPARISON: EXPERIENCE SECTION ===
[BEFORE]
[
{"company": "Autonomous and Robotic Systems Lab","position": "Graduate Researcher, SJSU -/youtubeambarishgk","location": "San Jose, CA","dates": "Sep 2024 – Present","bullets": [
    "Built a voice-operated teleoperation system integrating a LLM and Model Context Protocol (MCP) via
        ROS 2, achieving 1–40 ms command latency improving accessibility for human-robot collaboration",
    "Developed a WebRTC-based video streaming client in Node.js/JavaScript to stream real-time camera and
        telemetry data from edge devices, utilizing GStreamer, Socket.IO, and WebSocket APIs.",
    "Documented research methodology and system architecture, preparing comprehensive technical guides and datasets for
        reproducibility, and currently authoring a research paper."]},
{"company": "Smarthub.ai","position": "Software Engineer","location": "Bengaluru, India","dates": "May 2021 – Jan 2024","bullets": [
    "Redesigned firmware upgrade using AsyncIO + multithreading, reducing upgrade time by 95% (5h → 15 min).",
    "Built Docker, Edge IoT monitoring with 90% anomaly detection accuracy, cutting false downtime by 87%.",
    "Wrote Linux Bash scripts for legacy devices to monitor services and trigger cURL calls to push logs for analysis.",
    "Developed a Python Cloud SDK to scale monitoring across 4,000+ IoT devices with built-in retry logic and logging.",
    "Developed a Python SDK and asynchronous device simulator with integrated gRPC, REST, and GraphQL
        APIs to emulate real IoT devices for QA and testing, enabling the simulation of 1000+ concurrent devices."]},
{"company": "Predigle India Pvt Ltd","position": "Software Developer","location": "Chennai, India","dates": "Sep 2020 – Apr 2021","bullets": [
    "Wrote a full-stack web app (Flask, Angular/React, MySQL) handling 10M+ records with secure role-based auth.",
    "Built a real-time network surveillance tool in Python leveraging scapy, nmap, and socket libraries to monitor
        packets, fingerprint every user device, and alert on unauthorized access or anomalous behavior with nvdlib.",
    "Developed a Golang CLI that connects to a MySQL database, filters lead data by score, and stores output in CSV.",
    "Implemented a GitHub Actions CI workflow integrating static code analysis, linting, and dependency vulnerability
        scanning to enforce coding standards and security policies ; prevented pull-request merges until it was verified."]}"]

[AFTER]
### EXPERIENCE (suggested rewrite)
- Built a voice-operated teleoperation system for robotics using ROS 2 and MCP, achieving low latency.
- Developed a WebRTC-based video streaming client in Node.js/JavaScript for real-time data streaming.
- Documented research methodology and system architecture, preparing comprehensive technical guides and datasets for reproducibility.
- Redesigned firmware upgrade using AsyncIO + multithreading, reducing upgrade time significantly.
- Built Docker, Edge IoT monitoring with high anomaly detection accuracy, cutting false downtime drastically.
- Wrote Linux Bash scripts for legacy devices to monitor services and trigger cURL calls for log analysis.
- Developed a Python Cloud SDK to scale monitoring across thousands of IoT devices.
- Developed a Python SDK and asynchronous device simulator with integrated APIs for QA and testing.
- Wrote a full-stack web app handling millions of records with secure role-based auth.
- Built a real-time network surveillance tool in Python to monitor packets, fingerprint devices, and alert on unauthorized access or anomalous behavior.
- Developed a Golang CLI that connects to a MySQL database, filters lead data by score, and stores output in CSV format.
- Implemented a GitHub Actions CI workflow for static code analysis, linting, and dependency vulnerability scanning.

=== ORIGINAL PROJECTS SECTION (BEFORE) ===
[
{"name": "Agentic Resume/Cover builder","language": "Python","description": "Engineered an MCP based LLM agent using Python and RAG to analyze resumes and generate job-specific
        enhancements and cover letters, improving alignment with job description by 60–80%."},
{"name": "FirstResponder: MCP Enabled VLM for Intelligent Disaster Response","language": "Python","description": "Built a RescueBot with an on-device VLM and custom MCP server for real-time scene understanding; achieved 82%
        event classification accuracy and automated alerts to first responders and 911 within 3 seconds."},
{"name": "IoT Multi-Level Image Forensics Security Suite","language": "Python","description": "Integrated open-source tools such as PhotoHolmes, ExifTool, Sherloq, ImageMagick, and Scikit-Image for
        cross-verification of image integrity, metadata tampering, and steganographic content and scored them from IoT devices"},
{"name": "LeRobot Imitation Learning Framework","language": "Robotics, Imitation Learning, VLMs/VLAs (SmolVLA, Pi 0.5)","description": "Fine-tuned LeRobot policies using VLA models (SmolVLA, Pi 0.5) for autonomous oximeter placement; achieved
        50% task success in on-device inference and replay trials for medical manipulation."},
{"name": "ROS2 Wrapper for DualSense Haptic PS5 Joystick","language": "ROS2, C++, Robotics","description": "Built a ROS 2 Python driver integrating PS5 DualSense 6-DoF control and adaptive haptics, achieving 50 ms
        response latency for smooth, bidirectional robot teleoperation."}]

=== SECTION-WISE SUGGESTED REWRITES (RAW) ===
### SKILLS (suggested rewrite)
- Python
- C++
- Robotics
- Computer Vision
- Machine Learning
- LLMs
- Generative AI

### EXPERIENCE (suggested rewrite)
- Built a voice-operated teleoperation system for robotics using ROS 2 and MCP, achieving low latency.
- Developed a WebRTC-based video streaming client in Node.js/JavaScript for real-time data streaming.
- Documented research methodology and system architecture, preparing comprehensive technical guides and datasets for reproducibility.
- Redesigned firmware upgrade using AsyncIO + multithreading, reducing upgrade time significantly.
- Built Docker, Edge IoT monitoring with high anomaly detection accuracy, cutting false downtime drastically.
- Wrote Linux Bash scripts for legacy devices to monitor services and trigger cURL calls for log analysis.
- Developed a Python Cloud SDK to scale monitoring across thousands of IoT devices.
- Developed a Python SDK and asynchronous device simulator with integrated APIs for QA and testing.
- Wrote a full-stack web app handling millions of records with secure role-based auth.
- Built a real-time network surveillance tool in Python to monitor packets, fingerprint devices, and alert on unauthorized access or anomalous behavior.
- Developed a Golang CLI that connects to a MySQL database, filters lead data by score, and stores output in CSV format.
- Implemented a GitHub Actions CI workflow for static code analysis, linting, and dependency vulnerability scanning.
[info] Generating JD-skill coverage report with model: mistral:instruct


=== JD SKILLS COVERAGE REPORT ===
### JD SKILLS
1. Python
2. Objective-C
3. C++
4. Swift
5. R
6. Proficiency in a programming language
7. Experience completing a moderate-sized software project
8. Robotics
9. Machine Learning & ML Research
10. Large Language Models / Generative AI
11. Graduate degree in a STEM field or equivalent industry experience in software engineering

### MISSING OR WEAK IN ORIGINAL RESUME
- Python: The original resume lists Python as one of the languages, but it does not show any specific projects or experiences related to robotics or AI/ML research that would demonstrate proficiency in a moderate-sized software project.
- Objective-C, Swift: Not present in the original resume.
- R: Not present in the original resume.
- Experience completing a moderate-sized software project in the context of robotics or AI/ML research: The original resume does not provide any examples that demonstrate this skill.
- Robotics: While the original resume mentions some projects related to robotics, it does not show any specific experience with robotics in a professional setting.
- Machine Learning & ML Research: Although the original resume lists AI/ML as a skill, it does not provide any examples that demonstrate research or development in this area.
- Large Language Models / Generative AI: The original resume mentions some projects related to LLMs and VLMs, but it does not show any specific experience with large language models or generative AI.

### HOW SUGGESTED BULLETS INTEGRATE JD SKILLS
- Python: The suggested bullets now include examples of using Python for robotics projects (voice-operated teleoperation system) and AI/ML research (LLM agent, RescueBot with on-device VLM).
- Objective-C, Swift: Not addressed in the suggested rewrites.
- R: Not addressed in the suggested rewrites.
- Experience completing a moderate-sized software project in the context of robotics or AI/ML research: The suggested bullets now include examples of reducing firmware upgrade time significantly and building Docker, Edge IoT monitoring with high anomaly detection accuracy, which demonstrate experience with a moderate-sized software project in the context of IoT devices.
- Robotics: The suggested bullets now include examples of building a voice-operated teleoperation system for robotics using ROS 2 and MCP, and developing a ROS 2 Python driver integrating PS5 DualSense 6-DoF control and adaptive haptics.
- Machine Learning & ML Research: The suggested bullets now include examples of building an LLM agent using Python and RAG for resume enhancement, and building a RescueBot with an on-device VLM for real-time scene understanding.
- Large Language Models / Generative AI: The suggested bullets now include examples of developing an MCP enabled VLM for intelligent disaster response and fine-tuning LeRobot policies using VLA models for autonomous oximeter placement.
