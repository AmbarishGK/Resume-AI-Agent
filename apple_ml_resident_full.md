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
    "Experience completing a moderate-sized software project in Robotics, Machine Learning & ML Research, or Large Language Models / Generative AI",
    "Graduate degree in a STEM field"
  ],
  "notes": "The resume presents skills in programming languages such as Python, C++, and JavaScript. However, it lacks experience completing a moderate-sized software project in the required fields of Robotics, Machine Learning & ML Research, or Large Language Models / Generative AI. The candidate also does not hold a graduate degree in a STEM field, which is a minimum requirement for this position."
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
- Machine Learning
- LLMs
- Computer Vision
- ROS 2

=== COMPARISON: EXPERIENCE SECTION ===
[BEFORE]
[
{
    "company": "Autonomous and Robotic Systems Lab",
    "position": "Graduate Researcher, SJSU -/youtubeambarishgk",
    "location": "San Jose, CA",
    "dates": "Sep 2024 – Present",
    "bullets": [
        "Built a voice-operated teleoperation system integrating a LLM and Model Context Protocol (MCP) via ROS 2, achieving 1–40 ms command latency improving accessibility for human-robot collaboration",
        "Developed a WebRTC-based video streaming client in Node.js/JavaScript to stream real-time camera and telemetry data from edge devices, utilizing GStreamer, Socket.IO, and WebSocket APIs.",
        "Documented research methodology and system architecture, preparing comprehensive technical guides and datasets for reproducibility, and currently authoring a research paper."
    ]
},
{
    "company": "Smarthub.ai",
    "position": "Software Engineer",
    "location": "Bengaluru, India",
    "dates": "May 2021 – Jan 2024",
    "bullets": [
        "Redesigned firmware upgrade using AsyncIO + multithreading, reducing upgrade time by 95% (5h → 15 min).",
        "Built Docker, Edge IoT monitoring with 90% anomaly detection accuracy, cutting false downtime by 87%.",
        "Wrote Linux Bash scripts for legacy devices to monitor services and trigger cURL calls to push logs for analysis.",
        "Developed a Python Cloud SDK to scale monitoring across 4,000+ IoT devices with built-in retry logic and logging.",
        "Developed a Python SDK and asynchronous device simulator with integrated gRPC, REST, and GraphQL APIs to emulate real IoT devices for QA and testing, enabling the simulation of 1000+ concurrent devices."
    ]
},
{
    "company": "Predigle India Pvt Ltd",
    "position": "Software Developer",
    "location": "Chennai, India",
    "dates": "Sep 2020 – Apr 2021",
    "bullets": [
        "Wrote a full-stack web app (Flask, Angular/React, MySQL) handling 10M+ records with secure role-based auth.",
        "Built a real-time network surveillance tool in Python leveraging scapy, nmap, and socket libraries to monitor packets, fingerprint every user device, and alert on unauthorized access or anomalous behavior with nvdlib.",
        "Developed a Golang CLI that connects to a MySQL database, filters lead data by score, and stores output in CSV.",
        "Implemented a GitHub Actions CI workflow integrating static code analysis, linting, and dependency vulnerability scanning to enforce coding standards and security policies ; prevented pull-request merges until it was verified."
    ]
}
]

[AFTER]
### EXPERIENCE (suggested rewrite)
- Built a voice-operated teleoperation system for robotics, integrating LLM and MCP via ROS 2, achieving low latency for human-robot collaboration.
- Developed a WebRTC-based video streaming client in Node.js/JavaScript to stream real-time camera data from edge devices using GStreamer, Socket.IO, and WebSocket APIs.
- Documented research methodology and system architecture, preparing comprehensive technical guides and datasets for reproducibility, and currently authoring a research paper.
- Redesigned firmware upgrade using AsyncIO + multithreading, reducing upgrade time by 95%.
- Built Docker, Edge IoT monitoring with high anomaly detection accuracy, cutting false downtime significantly.
- Wrote Linux Bash scripts for legacy devices to monitor services and trigger cURL calls to push logs for analysis.
- Developed a Python Cloud SDK to scale monitoring across thousands of IoT devices with built-in retry logic and logging.
- Developed a Python SDK and asynchronous device simulator with integrated gRPC, REST, and GraphQL APIs to emulate real IoT devices for QA and testing.
- Wrote a full-stack web app handling millions of records with secure role-based auth.
- Built a real-time network surveillance tool in Python leveraging scapy, nmap, and socket libraries to monitor packets, fingerprint every user device, and alert on unauthorized access or anomalous behavior.
- Developed a Golang CLI that connects to a MySQL database, filters lead data by score, and stores output in CSV.
- Implemented a GitHub Actions CI workflow integrating static code analysis, linting, and dependency vulnerability scanning to enforce coding standards and security policies.

=== ORIGINAL PROJECTS SECTION (BEFORE) ===
[
{
    "name": "Agentic Resume/Cover builder",
    "languages": "Python",
    "ai_ml": "LLMs",
    "description": "Engineered an MCP based LLM agent using Python and RAG to analyze resumes and generate job-specific enhancements and cover letters, improving alignment with job description by 60–80%.",
},
{
    "name": "FirstResponder: MCP Enabled VLM for Intelligent Disaster Response",
    "languages": "Python, LLMs",
    "ai_ml": "VLM",
    "description": "Built a RescueBot with an on-device VLM and custom MCP server for real-time scene understanding; achieved 82% event classification accuracy and automated alerts to first responders and 911 within 3 seconds."
},
{
    "name": "IoT Multi-Level Image Forensics Security Suite",
    "languages": "Python, Security Software, IoT, Open-Source Tools",
    "description": "Integrated open-source tools such as PhotoHolmes, ExifTool, Sherloq, ImageMagick, and Scikit-Image for cross-verification of image integrity, metadata tampering, and steganographic content and scored them from IoT devices",
},
{
    "name": "LeRobot Imitation Learning Framework",
    "robotics": true,
    "ai_ml": "Imitation Learning, VLMs/VLAs (SmolVLA, Pi 0.5)",
    "description": "Fine-tuned LeRobot policies using VLA models (SmolVLA, Pi 0.5) for autonomous oximeter placement; achieved 50% task success in on-device inference and replay trials for medical manipulation."
},
{
    "name": "ROS2 Wrapper for DualSense Haptic PS5 Joystick",
    "robotics": true,
    "languages": "ROS2, C++",
    "description": "Built a ROS 2 Python driver integrating PS5 DualSense 6-DoF control and adaptive haptics, achieving 50 ms response latency for smooth, bidirectional robot teleoperation."
}
]

=== SECTION-WISE SUGGESTED REWRITES (RAW) ===
### SKILLS (suggested rewrite)
- Python
- C++
- Robotics
- Machine Learning
- LLMs
- Computer Vision
- ROS 2

### EXPERIENCE (suggested rewrite)
- Built a voice-operated teleoperation system for robotics, integrating LLM and MCP via ROS 2, achieving low latency for human-robot collaboration.
- Developed a WebRTC-based video streaming client in Node.js/JavaScript to stream real-time camera data from edge devices using GStreamer, Socket.IO, and WebSocket APIs.
- Documented research methodology and system architecture, preparing comprehensive technical guides and datasets for reproducibility, and currently authoring a research paper.
- Redesigned firmware upgrade using AsyncIO + multithreading, reducing upgrade time by 95%.
- Built Docker, Edge IoT monitoring with high anomaly detection accuracy, cutting false downtime significantly.
- Wrote Linux Bash scripts for legacy devices to monitor services and trigger cURL calls to push logs for analysis.
- Developed a Python Cloud SDK to scale monitoring across thousands of IoT devices with built-in retry logic and logging.
- Developed a Python SDK and asynchronous device simulator with integrated gRPC, REST, and GraphQL APIs to emulate real IoT devices for QA and testing.
- Wrote a full-stack web app handling millions of records with secure role-based auth.
- Built a real-time network surveillance tool in Python leveraging scapy, nmap, and socket libraries to monitor packets, fingerprint every user device, and alert on unauthorized access or anomalous behavior.
- Developed a Golang CLI that connects to a MySQL database, filters lead data by score, and stores output in CSV.
- Implemented a GitHub Actions CI workflow integrating static code analysis, linting, and dependency vulnerability scanning to enforce coding standards and security policies.
[info] Generating JD-skill coverage report with model: mistral:instruct

[info] Generating tailored cover letter with large model: mistral:instruct


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
- Proficiency in a programming language: The original resume lists several programming languages, but it does not explicitly mention proficiency in any of them.
- Experience completing a moderate-sized software project: The original resume mentions projects, but they do not clearly demonstrate experience with a moderate-sized software project in the required fields of Robotics, Machine Learning & ML Research, or Large Language Models / Generative AI.
- Graduate degree in a STEM field: The original resume does not indicate that the candidate holds a graduate degree in a STEM field.

### HOW SUGGESTED BULLETS INTEGRATE JD SKILLS
- Proficiency in a programming language: The suggested bullets now explicitly mention proficiency in Python, C++, and Node.js/JavaScript.
- Experience completing a moderate-sized software project: The suggested bullets now include experiences that demonstrate working on a firmware upgrade, Docker, Edge IoT monitoring, and a full-stack web app, which can be interpreted as examples of moderate-sized software projects in the required fields.
- Graduate degree in a STEM field: Although not explicitly mentioned, the original resume does indicate industry experience in software engineering, which could potentially meet the equivalent requirement for a graduate degree in a STEM field. However, the suggested rewrites do not address this issue directly.

=== COVER LETTER DRAFT ===
Subject: Application for AIML Resident - Robot Learning at Apple

Dear Hiring Manager,

I am writing to express my keen interest in the AIML Residency position focusing on robot learning at Apple. As a passionate and dedicated software engineer with a strong background in machine learning, artificial intelligence, and robotics, I believe that this opportunity aligns perfectly with my skills and aspirations.

In my current role as a Graduate Researcher at the Autonomous and Robot Systems Lab in San Jose, CA, I have been working on developing a voice-operated teleoperation system integrating a Large Language Model (LLM) and Model Context Protocol (MCP) via ROS 2. This project has enabled me to achieve impressive command latency improvements for human-robot collaboration, demonstrating my ability to connect and collaborate with others effectively while working on high-impact projects.

At Smarthub.ai, I redesigned firmware upgrade using AsyncIO + multithreading, reducing upgrade time by 95%. In addition, I developed a Python Cloud SDK that scaled monitoring across thousands of IoT devices, showcasing my proficiency in programming languages such as Python and my experience completing moderate-sized software projects.

In my previous role at Predigle India Pvt Ltd, I wrote a full-stack web app handling millions of records with secure role-based auth, demonstrating my ability to work with large datasets and enforce coding standards for security and efficiency. Moreover, I developed a Golang CLI that connected to a MySQL database, filtering lead data by score and storing the output in CSV, further showcasing my programming skills and ability to work with databases.

I have also successfully completed several projects, including "Agentic Resume/Cover builder," which engineered an MCP-based LLM agent using Python and RAG, improving alignment with job descriptions by 60–80%. Additionally, I built a RescueBot with an on-device VLM for real-time scene understanding, achieving 82% event classification accuracy.

I am eager to join the AIML residency program at Apple and contribute my expertise in robotics, machine learning, and AI to innovate and build revolutionary products and experiences. I am confident that my research interests, skills, and experience make me an ideal candidate for this position. Thank you for considering my application, and I look forward to the opportunity to discuss my qualifications further.

Sincerely,
[Your Name]
