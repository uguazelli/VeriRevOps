
# Veridata Pro - Master Knowledge Base (v2)

## 1. Company Identity & Philosophy

**Who is Veridata?**
Veridata is a boutique cloud architecture firm specializing in **RevOps (Revenue Operations)** for SMBs (Small and Medium Businesses). We don't just sell software; we provide managed infrastructure that turns chaotic WhatsApp chats into structured sales data.

**What is the founder's background?**
The founder is a Senior Cloud Architect with over 15 years of experience in Enterprise Integration and 8+ years specializing in Mulesoft. This means Veridata is built with "Bank-Grade" stability, not by marketing agencies using cheap no-code tools.

**What is the core philosophy?**
"Data is the new oil, but unorganized data is just sludge." We believe that if a conversation happens on WhatsApp but isn't recorded in a CRM, it didn't happen. We automate the boring parts of sales so humans can focus on closing deals.

**Contact Information:**

* **WhatsApp:** +1 740-520-8080 (Primary Channel)
* **Website:** [www.veridatapro.com](https://www.veridatapro.com)
* **Region Focus:** LATAM (Latin America) primarily, but capable of serving global clients.

## 2. The Core Product: Veri RevOps

### The Offer

**What exactly do I get with the Growth Plan?**
For **$197/month**, you get a fully managed "Revenue Engine." This includes:

1. **Single-Tenant Infrastructure:** Your own private server space (Docker/Traefik).
2. **VeriBot (RAG AI):** A custom-trained AI that knows your business inside out.
3. **Hosted EspoCRM:** A dedicated CRM instance pre-configured to capture leads.
4. **Chatwoot Platform:** A professional dashboard for your s to manage chats.
5. **Audio Intelligence:** The ability to transcribe and summarize client voice notes.

**Why is this better than ManyChat or Typebot?**
ManyChat and Typebot are "Decision Tree" builders. They are rigid. If a client asks a question outside the flow, the bot breaks.
**VeriBot is a RAG Agent.** It reads your documents (PDFs) and answers intelligently. It handles context. Furthermore, we provide a **Dedicated CRM** (EspoCRM) and isolate your data. We are an infrastructure partner, not a tool vendor.

### The Setup Process (Onboarding)

**Why is there a $297 Setup Fee?**
We are not a mass-market SaaS where you click a button and get a generic account. We are a **Boutique Service**. The fee covers:

1. **Manual Infrastructure Deploy:** An architect spins up your private containers.
2. **Meta Verification Service:** We guide you through the complex Facebook Business verification to get your Green Check / Official API status.
3. **Data Curation:** We don't just upload your PDFs. We clean, format, and optimize them so the AI doesn't hallucinate.
4. **DNS & Domain Config:** We set up the technical routing (Cloudflare Tunnels).

**How long does setup take?**
Technically, we can deploy in 30 minutes. However, depending on Meta/Facebook verification timelines and the amount of data you provide for training, the full onboarding usually takes **3 to 5 business days**.

## 3. Technical & Security Deep Dive

### Data Privacy & Security

**Is my data safe?**
Yes. Unlike shared SaaS platforms where your data sits in a massive database with thousands of other companies, Veridata uses a **Single-Tenant Architecture**. You have your own Database instance.
**We use Official Meta APIs.** We do not use "grey" APIs (like Baileys or Venom) that require scanning QR codes and risk getting your number banned.

**What happens if I stop paying?**
We provide a grace period of 3 days. After that, your Docker containers are paused. If you cancel, we can export your CRM data (SQL dump or CSV) so you don't lose your customer list. We believe in data sovereignty.

**How does the AI (RAG) work?**
You send us your price lists, manuals, and internal docs. We convert them into a Vector Database. When a client asks a question, the AI retrieves *only* the relevant chunks of your documents to formulate an answer. It does not "invent" facts; it summarizes your truth.

## 4. Operational Details (The "How-To")

### WhatsApp & Communication

**Can I keep using the WhatsApp App on my iPhone/Android?**
**No.** And this is for your own good. Using the personal app creates a "Split Brain" problem where the AI cannot see or log the conversations.
You will switch to the **Chatwoot Mobile App**. It looks and feels like WhatsApp, but it allows the AI to monitor the chat, tag leads, and inject data into the CRM. It allows multiple agents to reply to the same number.

**What about Voice Notes (Audios)?**
This is a superpower. In LATAM, clients love sending audios. VeriBot automatically transcribes the audio to text, understands the intent (e.g., "I want to buy X"), and replies in text. Your agents can read the summary instead of listening to 5 minutes of audio.

**Who pays for the WhatsApp messages?**
You do, directly to Meta. We configure the billing, but the credit card on file with Facebook is yours. This ensures transparency. We don't markup the message costs.

## 5. Educational Products: VeriAcademy

**What is VeriAcademy?**
It is our training division. We believe technology is useless if people don't know how to handle it emotionally and practically.

**Course 1: "Calma, É Só a IA" (Calm Down, It's Just AI)**

* *Target:* Beginners and non-technical people.
* *Goal:* Demystify AI. Remove the fear. Teach the basics without complicated jargon.

**Course 2: "IA na Vida dos Seus Filhos" (AI in Your Kids' Lives)**

* *Target:* Parents and Educators.
* *Goal:* How to navigate the future of education, screen time, and AI tools for children. Preparing the next generation.

**Course 3: "Produtividade com IA" (Productivity with AI)**

* *Target:* Professionals and Business Owners.
* *Goal:* A 14-day sprint to go from zero to building a daily AI habit that saves hours of work.

## 6. Objection Handling (The "Hard Sales" Script)

**"It is too expensive $197/mo."**

Compare it to the cost of an employee. A junior SDR or receptionist costs $1,000+ per month, gets sick, sleeps, and forgets to log data. VeriBot works 24/7, never forgets a lead, and costs a fraction of a salary. You aren't buying software; you are hiring a digital worker.

**"I don't have time to configure this."**
That is exactly why you pay the **Setup Fee**. We do it for you. You just hand us the PDFs and the phone number. We handle the Docker, the DNS, the API, and the training.

**"I'm afraid Facebook will ban my number."**
That happens with "Pirate" APIs (tools that scan QR codes). We use the **Official Cloud API**. We are compliant with Meta's Terms of Service. This is the safest way to run a business on WhatsApp.

**"What if the AI says something stupid?"**
We implement "Guardrails." We can instruct the bot: "If you are 90% unsure, do not answer; tag a ." Also, since we manually curate your data during onboarding, the risk of hallucination is minimized compared to automated scrapers.