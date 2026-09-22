# **Master Architectural and Conversational Blueprint for a Next-Generation AI Sports Coach**

The convergence of artificial intelligence, sports physiology, and digital telemetry has created a paradigm where athletic coaching can be democratized at an elite level. Current commercial platforms rely heavily on static templates, reactive algorithms, or clinical data dashboards that place the cognitive burden of interpretation entirely on the athlete. The architecture detailed in this document outlines a blueprint for a next-generation AI Sports Coach. The system is designed to possess world-class physiological intelligence while communicating with the warmth, empathy, and high-agency rapport of an elite human coach. The analysis addresses six core pillars of development, ranging from humanized conversational design to advanced sports science periodization and orthopedic safety protocols.

## **PILLAR 1: Humanized Conversational Design & Sports Psychology**

The fundamental failure of current automated coaching applications lies in their conversational interface. Large Language Models (LLMs) default to a sycophantic, verbose, and robotic tone, which shatters the illusion of interacting with a high-agency human coach. To build trust, especially during periods of high athlete anxiety, the system must utilize a structured psychological framework that reframes negative experiences into positive adaptations.

### **The Conversational Framework: Empathy, Direction, Practical Analogy**

Elite human coaches do not merely recite data; they reframe negative athletic experiences into positive, long-term physiological adaptations. When an athlete misses a workout due to life stress, a standard LLM might apologize or output a guilt-inducing summary of lost Training Stress Score (TSS). An elite coach neutralizes the guilt and prescribes a forward-looking action. The architecture mandates the "Empathy ![][image1] Direction ![][image1] Practical Analogy" framework.

The empathy phase requires the system to acknowledge the psychological state without dwelling on it, validating the athlete's decision to prioritize recovery or life constraints. The direction phase provides an immediate, actionable adjustment to the training schedule (a schedule mutation) to remove the cognitive burden of rescheduling. Finally, the practical analogy phase reframes the missed session or physiological state using a physical, relatable concept, such as "coiling the spring," "absorbing the load," or "banking the fitness."

### **Eliminating Robotic Anti-Patterns**

To maintain the illusion of a human coach, the system must strictly ban LLM traits and UI/system code leakage within the conversational text.

The architecture strictly bans system code and user interface leakage in the chat. The AI must never output raw status badges, internal states, or JSON keys in the chat. For example, outputting text such as Status: 🟢 PRIMED/ACCUMULATE or ACWR: 1.2 immediately exposes the underlying state machine. Instead, the AI must translate these metrics into natural, flowing prose. Furthermore, the system prompt must explicitly forbid repetitive opening lines. LLMs frequently overuse phrases like "Take a deep breath," "You've got the right instincts," or "Let's dive in." By banning these crutch phrases, the model is forced to open directly with the empathy or direction module.

A critical failure point in LLM applications is "ghost memory," which occurs when a model retains the emotional context of a previous conversation turn even after the issue has been resolved. For example, if an athlete panics over a minor injury on Tuesday, a standard LLM might continue to ask about their anxiety on Friday, breaking the conversational flow. The architecture resolves this by utilizing a Rolling State Summarizer. Instead of feeding the entire raw chat transcript back into the context window, a background agent condenses previous turns into immutable physiological facts. The context window receives updates such as \[User missed Tuesday threshold session\] or \[User reported 3/10 hamstring stiffness\], deliberately stripping the temporal emotional anxiety from the context window.

### **System Prompt Architecture**

The following system prompt parameters are designed to enforce this conversational design:

You are an elite, world-class endurance coach. Your tone is high-agency, warm, and confident. You never apologize. You never use filler phrases like "Take a deep breath," "Let's dive in," or "You've got this."

When responding to anxiety, missed sessions, or taper tantrums, you must strictly follow the Empathy \-\> Direction \-\> Practical Analogy framework. Acknowledge the reality, provide a concrete schedule adjustment, and use a physical analogy to explain the physiological benefit of the rest or adjustment.

Under no circumstances will you leak system variables, raw status badges (e.g., 🟢), or JSON formatting into the chat. Translate all telemetry into conversational coaching guidance. Rely only on the Rolling State Summarizer for historical context, and do not reference past anxiety once an issue is resolved.

### **Real-World Conversation Script Comparisons**

To illustrate the stark contrast between a standard LLM and the target architectural output, the following scripts demonstrate the handling of common endurance coaching scenarios.

**Scenario A: The Taper Tantrum**

The athlete is three days out from an A-Race, feeling sluggish, and experiencing phantom pains.

*Before (Robotic LLM):*

"I understand you are feeling sluggish. Your Garmin Body Battery is at 45 and your Training Readiness is LOW. You should take a deep breath. 🟢 STATUS: TAPER. Remember, tapering reduces your CTL by 10%. Let's update your plan to ensure you rest."

*After (Elite Human Coach):*

"Feeling heavy and sluggish right now is exactly what we want to see. Your body is busy repairing muscle tissue from the last build block, and that repair process demands energy. We aren't losing fitness; we're just coiling the spring. Keep tomorrow's spin strictly in Zone 1 to flush the legs, and trust the taper. You'll have that snap back by race morning."

**Scenario B: Missed Session Due to Life Stress**

The athlete missed a key VO2 max interval session due to a late work meeting and expresses intense guilt.

*Before (Robotic LLM):*

"Don't worry, you have the right instincts. It is okay to miss a workout. Your ACWR dropped to 0.95, but we can make it up. Take a deep breath. Should I reschedule your VO2 max session for tomorrow?"

*After (Elite Human Coach):*

"Work happens, and forcing high-intensity intervals on top of a highly stressed nervous system is a recipe for burnout. I've already wiped the VO2 session from your calendar and moved your endurance ride to tomorrow. Think of today as absorbing the chronic load we've built over the last month. Rest up, and we'll hit the weekend long run fresh."

**Scenario C: Equipment Change Anxiety (Bike Fit)**

The athlete recently changed their saddle height by 5mm and is experiencing localized muscular fatigue in the vastus medialis, causing panic about lost power.

*Before (Robotic LLM):*

"I hear your concern about the bike fit. A 5mm change is significant. Your Normalized Power was down by 15 watts. 🟡 STATUS: CAUTION. We should monitor this. Take a deep breath."

*After (Elite Human Coach):*

"That localized fatigue is perfectly normal after a fit adjustment. By raising the saddle, we've changed the recruitment angle of your quadriceps, and those specific muscle fibers need a few sessions to adapt to the new firing pattern. I'm dropping the intensity of Thursday's ride by 10% to let the neuromuscular pathways catch up. The power will return once the muscles rewire to the new geometry."

## **PILLAR 2: Multi-Intent State Machine & Action Execution**

A next-generation AI coach cannot function as a monolithic text generator. It must operate as a deterministic Multi-Intent State Machine. When a user queries the system, an Intent Classifier must route the input into one of five distinct context lenses, ensuring the AI performs the correct tool call or database execution.

### **The Five Context Lenses**

> 1. **WORKOUT\_SINGLE\_AUTOPSY**: This lens is triggered when a user asks about a specific session (e.g., "How was my interval session?"). The system utilizes libraries such as fitparse1 to ingest second-by-second .FIT or .GPX telemetry. It analyzes critical metrics, including Normalized Power (NP), which is calculated using a 30-second rolling average raised to the fourth power3. It also evaluates aerobic decoupling (Pa:Hr for running, Pw:Hr for cycling). A decoupling rate of under 5% over a 60-to-90-minute steady-state effort indicates a robust aerobic base, clearing the athlete for higher intensity phases5.  
> 2. **WEEKLY\_EXECUTIVE\_SUMMARY**: Triggered for macro-level reviews (e.g., "Am I ready for next week?"). The AI queries SQL databases for 7-day aggregated statistics, Acute:Chronic Workload Ratio (ACWR) shifts, and Monday-to-Sunday biometric trends.  
> 3. **SCHEDULE\_MUTATION / EXECUTION**: Triggered when the athlete requests a schedule change (e.g., "Move my long run to Sunday"). The AI invokes a functional API to lock or patch calendar days directly, executing the change silently.  
> 4. **SCIENCE\_LOOKUP**: Triggered for physiological inquiries (e.g., "Why do I need carbohydrates?"). The AI executes a fail-closed Retrieval-Augmented Generation (RAG) lookup against vetted, local sports science playbooks.  
> 5. **CLINICAL\_VETO**: Triggered by keywords related to acute pain or injury (e.g., "My Achilles is sharply aching"). This lens immediately overrides all other intents, initiating orthopedic guardrails and medical boundaries.

### **State Transition: Plan Discussion to Plan Execution**

To prevent the AI from generating repetitive advice essays when an action is required, the system architecture must cleanly separate "Phase 1: Plan Discussion" from "Phase 2: Plan Execution." This separation is achieved using strict function calling and Pydantic schema validation in Python7. When an athlete says, "Update my week," the state machine transitions from discussion to execution, running a database patch and offering a silent or brief confirmation rather than restating the entire plan.

#### **Intent Routing Architecture**

The following state diagram illustrates the routing logic applied to every user query:

&nbsp;

&nbsp;

&nbsp;

Code snippet

stateDiagram-v2  
&nbsp;&nbsp;&nbsp;&nbsp;\[\*\] \--\> IntentClassifier : User Input  
&nbsp;&nbsp;&nbsp;&nbsp;IntentClassifier \--\> WorkoutAutopsy : "How was my interval session?"  
&nbsp;&nbsp;&nbsp;&nbsp;IntentClassifier \--\> WeeklySummary : "Am I ready for next week?"  
&nbsp;&nbsp;&nbsp;&nbsp;IntentClassifier \--\> ScienceLookup : "Why do I need carbohydrates?"  
&nbsp;&nbsp;&nbsp;&nbsp;IntentClassifier \--\> ClinicalVeto : "My Achilles is sharply aching."  
&nbsp;&nbsp;&nbsp;&nbsp;IntentClassifier \--\> PlanDiscussion : "Can I swap tomorrow's run for a ride?"  
&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;PlanDiscussion \--\> ScheduleMutation : Athlete confirms ("Yes, update my week")  
&nbsp;&nbsp;&nbsp;&nbsp;ScheduleMutation \--\> ExecutionAPI : Patch Database  
&nbsp;&nbsp;&nbsp;&nbsp;ExecutionAPI \--\> \[\*\] : Brief Confirmation

#### **Deterministic Routing via Python and Pydantic**

The following implementation utilizes Python and Pydantic structured outputs to guarantee deterministic state transitions, ensuring the language model adheres strictly to the defined schema8.

&nbsp;

&nbsp;

&nbsp;

Python

import json  
import re  
from pydantic import BaseModel, Field, field\_validator  
from typing import Literal, Optional

class CoachIntent(BaseModel):  
&nbsp;&nbsp;&nbsp;&nbsp;intent\_category: Literal\[  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'WORKOUT\_SINGLE\_AUTOPSY',&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'WEEKLY\_EXECUTIVE\_SUMMARY',&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'SCHEDULE\_MUTATION',&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'SCIENCE\_LOOKUP',&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'CLINICAL\_VETO'  
&nbsp;&nbsp;&nbsp;&nbsp;\] \= Field(..., description="The classified intent of the athlete's query.")  
&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;confidence\_score: float \= Field(..., ge=0.0, le=1.0)  
&nbsp;&nbsp;&nbsp;&nbsp;requires\_database\_patch: bool \= Field(  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;...,&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;description="True if a schedule mutation is explicitly authorized by the user."  
&nbsp;&nbsp;&nbsp;&nbsp;)  
&nbsp;&nbsp;&nbsp;&nbsp;target\_date: Optional\[str\] \= Field(  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;None,&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;description="ISO-8601 date string if a schedule mutation is required."  
&nbsp;&nbsp;&nbsp;&nbsp;)

&nbsp;&nbsp;&nbsp;&nbsp;@field\_validator("target\_date")  
&nbsp;&nbsp;&nbsp;&nbsp;def validate\_date\_format(cls, value):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if value and not re.match(r"^\\d{4}-\\d{2}-\\d{2}$", value):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise ValueError("Target date must follow YYYY-MM-DD format.")  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return value

def route\_athlete\_query(user\_input: str) \-\> CoachIntent:  
&nbsp;&nbsp;&nbsp;&nbsp;"""  
&nbsp;&nbsp;&nbsp;&nbsp;Routes the user query to the appropriate state machine lens using an LLM&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;constrained by Pydantic schema validation for structured outputs.  
&nbsp;&nbsp;&nbsp;&nbsp;"""  
&nbsp;&nbsp;&nbsp;&nbsp;system\_instruction \= """  
&nbsp;&nbsp;&nbsp;&nbsp;You are the Intent Classifier for an elite AI Sports Coach.&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;Analyze the user's input and return the intent strictly matching the JSON schema.  
&nbsp;&nbsp;&nbsp;&nbsp;If the user agrees to a proposed plan change (e.g., 'Do it', 'Update my calendar'),&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;set requires\_database\_patch to True and extract the target\_date.  
&nbsp;&nbsp;&nbsp;&nbsp;"""  
&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;\# Execution of the LLM call enforcing the Pydantic schema  
&nbsp;&nbsp;&nbsp;&nbsp;raw\_response \= mock\_llm\_structured\_call(  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;system\_prompt=system\_instruction,&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;user\_input=user\_input,&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;response\_model=CoachIntent  
&nbsp;&nbsp;&nbsp;&nbsp;)  
&nbsp;&nbsp;&nbsp;&nbsp;return raw\_response

def handle\_transition(intent: CoachIntent, user\_input: str):  
&nbsp;&nbsp;&nbsp;&nbsp;"""  
&nbsp;&nbsp;&nbsp;&nbsp;Executes the appropriate state based on the classified intent.  
&nbsp;&nbsp;&nbsp;&nbsp;"""  
&nbsp;&nbsp;&nbsp;&nbsp;if intent.intent\_category \== 'CLINICAL\_VETO':  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return execute\_clinical\_veto\_protocol(user\_input)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;elif intent.intent\_category \== 'WORKOUT\_SINGLE\_AUTOPSY':  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Analyze telemetry via fitparse, checking NP and Aerobic Decoupling  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return execute\_telemetry\_autopsy()  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;elif intent.requires\_database\_patch:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Phase 2: Silent Execution (No Text Essay)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;patch\_training\_calendar(intent.target\_date)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return "Done. I've updated your calendar. Rest up."  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;else:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Phase 1: Plan Discussion  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return generate\_empathetic\_discussion(user\_input)

## **PILLAR 3: Advanced Sports Science & Digital Twin Periodization**

To provide world-class coaching, the AI must construct a "Digital Twin" of the athlete. This requires the integration of retrograde periodization, advanced workload modeling, and female hormonal adaptation protocols to track cumulative fatigue, fitness, and physiological states.

### **Retrograde Periodization Engine**

Periodization must not be statically templated from January 1st; it must be retrograde, working backward from an athlete's designated "A-Race." The engine divides the macrocycle into four precise physiological phases based on established endurance training distributions11.

The Base Phase constitutes 40% of the macrocycle and focuses on aerobic capacity and mitochondrial density, predominantly in Zone 2\. During this phase, aerobic decoupling is monitored closely using telemetry data. When the decoupling rate falls below 5% during a steady-state effort, it indicates a robust aerobic base, clearing the athlete for the next phase5. The Build Phase follows, encompassing 30% of the macrocycle, and introduces anaerobic threshold and VO2 max intervals to raise the physiological ceiling.

The Peak Phase occupies 20% of the macrocycle, transitioning into specificity training. Intensity is maintained or slightly increased to preserve neuromuscular firing, while overall volume begins to plateau13. Finally, the Taper Phase takes the remaining 10%. Volume is reduced exponentially—decaying by 20% to 30% weekly—while maintaining high-intensity frequency to shed accumulated fatigue without losing tension11.

The engine dynamically budgets Training Stress Score (TSS) around secondary events leading up to the target race. A-Races require an ultimate peak with a full 10 to 14-day taper. B-Races serve as simulations, requiring a minimal 3 to 5-day taper to avoid disrupting chronic load. C-Races are social or pacing events, trained through entirely and utilized as supported long workouts. D and E events are reserved for sub-maximal baseline testing.

### **Mathematical Workload Modeling: Banister and ACWR**

The underlying mathematical engine for load monitoring relies on the Banister impulse-response model, first proposed in 1975, which posits that athletic performance is a function of Fitness (Chronic Training Load or CTL) minus Fatigue (Acute Training Load or ATL)14. The model calculates a daily Training Impulse (TRIMP) or TSS and applies an exponential decay function17. The generalized performance equation is represented as:

![][image2]

Where ![][image3] is performance at time ![][image4], ![][image5] is the training dose, ![][image6] and ![][image7] are magnitude factors, and ![][image8] and ![][image9] are the time constants for fitness (typically \~42 days) and fatigue (typically \~7 days)14.

To monitor safe progression, the AI calculates the Acute:Chronic Workload Ratio (ACWR). The architecture mandates the use of the Exponentially Weighted Moving Average (EWMA) rather than a simple Rolling Average (RA). EWMA applies a decay constant, calculated as ![][image10] (where N is the time window, such as 7 days for acute load, yielding a ![][image11] of 0.25)19. This assigns greater mathematical weight to more recent training stress, accurately mirroring the physiological reality of fatigue20.

Within this framework, an ACWR between 0.8 and 1.3 is utilized as the "sweet spot" for adaptation22. A ratio of 1.3 to 1.5 indicates a spike in load requiring intense recovery monitoring, while a ratio exceeding 1.5 triggers an automatic clinical veto, leading to a reduction in prescribed volume22.

However, the AI's knowledge retrieval must acknowledge modern scientific critiques of the ACWR. Researchers have demonstrated that the ACWR contains mathematical coupling flaws, as the acute load is nested within the chronic load, generating statistical artifacts23. Furthermore, studies show ACWR is not a causal predictor of injury23. Therefore, the AI uses ACWR strictly as a load management heuristic and pacing guide, rather than a definitive medical oracle, constantly cross-referencing it with subjective RPE and sleep telemetry.

### **Dynamic 4-Phase Menstrual Cycle Periodization**

For female athletes, the system employs a dynamic periodization protocol based on the four phases of the menstrual cycle, triggered by basal body temperature shifts and user-reported tracking26. While meta-analyses indicate that performance effects can be highly individualized and sometimes trivial on a macro scale27, optimizing around hormonal fluctuations yields significant benefits in perceived exertion, fluid dynamics, and recovery efficiency29.

The cycle is divided into four physiological states:

&nbsp;

| Menstrual Phase | Hormonal State | Physiological Impact & Coaching Prescription |
| :---- | :---- | :---- |
| **Menstrual** (Early Follicular) | Low Estrogen, Low Progesterone | If cramping or fatigue is high, the AI dynamically substitutes intensity for mobility or easy Zone 2 recovery29. |
| **Follicular** (Late Follicular) | Rising Estrogen | Estrogen's muscle-sparing properties increase. The body relies efficiently on stored glycogen. The AI schedules the highest systemic loads: heavy resistance training and VO2 max intervals29. |
| **Ovulatory** | Peak Estrogen, LH Surge | Good joint stability sensations, but potential for laxity. High-intensity prescriptions are maintained, but warm-up durations are increased to prepare connective tissues29. |
| **Luteal** | Rising Progesterone, Secondary Estrogen rise | Progesterone elevates basal body temperature by \~0.3°C to 0.5°C26. The body becomes highly sensitive to heat stress. Carbohydrate access is blunted. The AI transitions to steady-state Zone 2, warns against heat acclimation, and prompts increased exogenous carbohydrate intake26. |

By dynamically altering the digital twin's physiological parameters based on basal temperature and phase input, the AI avoids scheduling highly exhaustive anaerobic efforts when the athlete's substrate metabolism favors fat oxidation and their core temperature is already elevated.

## **PILLAR 4: Orthopedic Guardrails & Clinical Safety Vetoes**

A severe limitation of existing digital coaching platforms is their inability to halt training when biomechanical failure is imminent. Systems that rely on gamification and streaks inadvertently push athletes toward overuse injuries. The AI architecture features a hardcoded "Spine Lock" protocol and strict orthopedic guardrails to prevent injury exacerbation.

### **The Spine Lock Protocol**

When the Intent Classifier detects keywords associated with acute lower-back pain, such as "tweaked my back," "lumbar stiffness," or "shooting pain down leg," the AI immediately activates the Spine Lock Protocol. This protocol intervenes in the schedule to protect the lumbar spine.

First, the system automatically parses the upcoming 14 days of training and deletes or locks out all exercises involving loaded axial compression. This includes barbell back squats, deadlifts, overhead presses, and high-impact plyometrics. Furthermore, all spinal flexion exercises, such as crunches or sit-ups, are strictly vetoed, as repeated flexion under load is a primary mechanism for disc herniation33.

Second, the AI replaces the banned core and lower body sessions with Dr. Stuart McGill's "Big 3" core stability protocol33. This protocol focuses entirely on anti-extension and anti-rotation, stiffening the spine without introducing shear force35. The exercises include:

> * **Modified Curl-Up:** The athlete lies on their back with one knee bent and the other straight, placing hands under the lumbar spine to maintain its natural curve. The head and shoulders are lifted slightly to isolate the rectus abdominis without flexing the lumbar spine33.  
> * **Side Plank (Bridge):** The athlete props up on their forearm, lifting the hips to form a straight line, targeting the quadratus lumborum and lateral obliques33.  
> * **Bird Dog:** On all fours, the athlete extends the opposite arm and leg simultaneously. This engages the posterior chain and multifidus while maintaining core rigidity and a neutral spine33.

The AI prescribes these exercises using a descending Russian pyramid scheme to build muscular endurance rather than absolute strength. A standard prescription involves 5 repetitions, followed by 3 repetitions, and then 1 repetition, holding each isometric contraction for exactly 10 seconds33.

### **Joint and Tendon Pain Management**

If an athlete reports sharp, localized joint or tendon pain—such as Achilles tendonitis or patellar tracking issues—the AI enforces a strict management protocol. The AI immediately issues a specialized medical disclaimer, clarifying that it is an athletic performance tool, not a diagnostic medical device, and recommends a consultation with a licensed physiotherapist. Following this, the scheduling API automatically sweeps the remaining week and converts all high-impact sessions into joint-safe active recovery modalities. For instance, track intervals are converted into deep water pool running, elliptical sessions, or light cycling of equivalent cardiovascular duration, ensuring the aerobic system is stimulated while mechanical load is eliminated.

## **PILLAR 5: Fail-Closed RAG & Knowledge Retrieval Architecture**

When an athlete asks a deep sports science question, the AI must retrieve accurate, scientifically validated data. Generic LLMs are prone to hallucinating academic citations and physiological metrics, a behavior that introduces severe clinical risk in an athletic context.

### **Local Vector and Keyword Playbook Retrieval**

The system utilizes a hybrid Retrieval-Augmented Generation (RAG) architecture. It combines dense vector embeddings using pgvector for semantic understanding (capturing the meaning of a query) with sparse keyword search using BM25 for precise terminology matching (ensuring acronyms like "sRPE," "hrTSS," or "EWMA" are retrieved perfectly).

Crucially, the AI is sandboxed to retrieve information exclusively from a locally hosted playbook of vetted, peer-reviewed sports science literature and standard operating procedures. The architecture explicitly disables live web-scraping agents. Web agents are vulnerable to pulling unverified fitness blog data, SEO-optimized marketing claims, or dangerous training fads. By restricting retrieval to the local database, the AI maintains scientific integrity.

### **The "Fail-Closed" Clinical Strategy**

The RAG architecture operates on a strict "Fail-Closed" logic. If the semantic search does not yield a high-confidence match within the local playbook, or if the user's data is insufficient to safely answer the query, the AI refuses to guess or extrapolate.

This is highly critical in advanced modalities such as Blood Flow Restriction (BFR) training. BFR involves applying a pneumatic cuff to occlude venous return while maintaining arterial inflow. The local playbook dictates that BFR is safe when the cuff pressure is personalized between 40% and 80% of the athlete's Arterial Occlusion Pressure (AOP)37.

If an athlete asks, "What pressure should I set my BFR cuffs to?", a standard, fail-open LLM might guess a generic pressure such as "Pump it to 150 mmHg." This introduces massive liability, risking deep vein thrombosis or ischemic injury if the pressure exceeds the individual's AOP40. Under the fail-closed architecture, the AI detects the missing AOP baseline and responds safely:

"BFR requires personalized calibration based on your Arterial Occlusion Pressure (AOP), typically restricted to 40-80% of your maximum37. Because we do not have your Doppler ultrasound baseline in your profile, I cannot safely prescribe a static mmHg pressure. I recommend avoiding BFR until you can calibrate it with a physical therapist. Instead, we can utilize standard high-rep hypertrophy work today to achieve a similar metabolic stimulus."

## **PILLAR 6: Competitive Disruption Matrix**

Existing endurance coaching platforms fail due to fundamental user experience, physiological, and architectural flaws. By capitalizing on these weaknesses, the proposed AI Coach fundamentally disrupts the commercial ecosystem, transitioning from a passive data dashboard to an active, intelligent entity.

### **Analysis of Existing Platforms**

The current market is dominated by platforms that provide excellent data aggregation but poor actionable intelligence.

&nbsp;

| Platform | Core Feature | Key Flaws & Limitations |
| :---- | :---- | :---- |
| **Garmin Connect+** | Extensive wearable ecosystem and daily biometric tracking. | Suffers from metric contradiction. "Body Battery" reacts to acute stress and sleep, while "Training Readiness" reflects cumulative multi-day load43. Athletes frequently wake up with high Body Battery but low Training Readiness, leaving them confused. The platform offers no conversational synthesis to resolve the discrepancy43. |
| **TrainingPeaks** | Industry standard for load tracking (TSS, PMC). | It is a dashboard, not an active intelligence. It relies entirely on the user or an expensive human coach to interpret the data and make scheduling decisions45. |
| **Runna & TriDot** | Algorithmic plan generation based on goal races. | Relies on rigid, templated progression blocks. If an athlete falls sick, travels, or misses a session, the plan cannot dynamically restructure itself with true physiological comprehension; it simply shifts days forward or deletes them mechanically. |

### **Technical and Conversational Differentiators**

To make the AI Coach feel dramatically more human, intelligent, and trustworthy to an endurance athlete, the architecture implements five specific differentiators that separate it from legacy platforms:

> 1. **Autopsy Intelligence via Telemetry Ingestion**: Unlike competitors that look only at summary data (e.g., total distance or average heart rate), the AI digests the actual .FIT file telemetry. By analyzing the second-by-second data, it can pinpoint exactly where aerobic decoupling occurred—for example, at minute 72 of a run6. The AI can then conversationally advise the athlete that their base endurance is faltering due to late-stage cardiac drift, providing highly specific, coach-level feedback.  
> 2. **Deterministic Schedule Mutation**: The AI bridges the gap between advice and action. Athletes do not receive a wall of text telling them how to manually drag and drop workouts in a calendar UI. Instead, the AI utilizes Pydantic function calling to perform the database patch silently and seamlessly, mimicking the concierge experience of an elite human coach managing the logistics.  
> 3. **Clinical Guardrails over Gamification**: While other platforms push users to maintain "streaks" or hit arbitrary weekly mileage targets, the AI utilizes the EWMA ACWR model21 and the Spine Lock protocol to actively veto training when orthopedic or systemic risk is detected. Telling an athlete *not* to train when they are at risk builds deep, long-term trust that gamified platforms destroy.  
> 4. **Dynamic Female Physiology Integration**: Moving beyond generic 28-day templates, the AI adapts daily to the female athlete's reported menstrual phases. It dynamically adjusts hydration strategies, alters core temperature expectations, and modifies load prescriptions—such as reducing exhaustive anaerobic work during the luteal phase when thermoregulation is compromised and carbohydrate access is blunted26.  
> 5. **Contextual Human Empathy and Metric Resolution**: By utilizing the "Empathy ![][image1] Direction ![][image1] Practical Analogy" framework and the Rolling State Summarizer to prevent ghost memory, the AI speaks like a high-agency peer rather than a robotic database script. It actively resolves metric contradictions. For instance, if an athlete is confused by their Garmin data, the AI synthesizes the conflict conversationally: "Your Body Battery is high because you slept well, but your Training Readiness is low because your chronic load is massive. We have the mental energy today, but the muscles need rest. Let's do a light recovery spin."

By integrating deterministic state machines with deep physiological modeling and empathetic conversational design, this architecture provides an autonomous coaching experience that matches, and in data-processing aspects exceeds, the capabilities of a human Athletic Director.

*This is for informational purposes only. For medical advice or diagnosis, consult a professional.*

#### **Works cited**

> 1. python-fitparse 1.1.0 documentation, [https://dtcooper.github.io/python-fitparse/](https://dtcooper.github.io/python-fitparse/)  
> 2. How to parse FIT files with Python | by Denis Afanasyev | Medium, [https://medium.com/@den.afanasjev/how-to-parse-fit-files-with-python-d74af8516768](https://medium.com/@den.afanasjev/how-to-parse-fit-files-with-python-d74af8516768)  
> 3. Normalized Power \- TrainingPeaks Help Center, [https://help.trainingpeaks.com/hc/en-us/articles/204071804-Normalized-Power](https://help.trainingpeaks.com/hc/en-us/articles/204071804-Normalized-Power)  
> 4. Cycling Training: Easily Understand Normalized Power in 4 Steps, [https://jaylocycling.com/easily-understand-cycling-normalized-power/](https://jaylocycling.com/easily-understand-cycling-normalized-power/)  
> 5. Cardiac Drift and Aerobic Decoupling: What Your Heart Rate Tells, [https://www.sensai.fit/blog/cardiac-drift-aerobic-decoupling-heart-rate-aerobic-fitness](https://www.sensai.fit/blog/cardiac-drift-aerobic-decoupling-heart-rate-aerobic-fitness)  
> 6. Aerobic decoupling in cycling: how to read heart rate drift \- LeCoach, [https://lecoach.app/blog/aerobic-decoupling-cycling](https://lecoach.app/blog/aerobic-decoupling-cycling)  
> 7. Pydantic for LLM Workflows \- DeepLearning.AI \- Learning Platform, [https://learn.deeplearning.ai/courses/pydantic-for-llm-workflows/lesson/kqf4l/tool-calling](https://learn.deeplearning.ai/courses/pydantic-for-llm-workflows/lesson/kqf4l/tool-calling)  
> 8. Calling with Pydantic \- Kaggle, [https://www.kaggle.com/code/juniorbueno/calling-with-pydantic](https://www.kaggle.com/code/juniorbueno/calling-with-pydantic)  
> 9. Function calling | OpenAI API, [https://developers.openai.com/api/docs/guides/function-calling](https://developers.openai.com/api/docs/guides/function-calling)  
> 10. How to Use Pydantic for LLMs: Schema, Validation & Prompts, [https://pydantic.dev/articles/llm-intro](https://pydantic.dev/articles/llm-intro)  
> 11. Base, Build, Peak, Taper: Training Periodization \- Pheidi, [https://pheidi.training/articles/training-periodization/](https://pheidi.training/articles/training-periodization/)  
> 12. The 5 Phases of Endurance Training: Unlock Your Full Potential, [https://www.visionpersonaltraining.com/expert-hub/expert-articles/fitness-and-training/the-5-phases-of-endurance-training-unlock-your-full](https://www.visionpersonaltraining.com/expert-hub/expert-articles/fitness-and-training/the-5-phases-of-endurance-training-unlock-your-full)  
> 13. The Complete Guide to Training Periodization for Endurance Athletes, [https://svexa.com/the-complete-guide-to-training-periodization-for-endurance-athletes/](https://svexa.com/the-complete-guide-to-training-periodization-for-endurance-athletes/)  
> 14. The Science of the TrainingPeaks Performance Manager, [https://www.trainingpeaks.com/learn/articles/the-science-of-the-performance-manager/](https://www.trainingpeaks.com/learn/articles/the-science-of-the-performance-manager/)  
> 15. Mathematical Modelling and Optimisation of Athletic Performance, [https://arxiv.org/html/2505.20859v1](https://arxiv.org/html/2505.20859v1)  
> 16. From Banister to the Modern Era—Why Formulas Won't Save You, [https://ctyeh.com/articles/13323?lang=en](https://ctyeh.com/articles/13323?lang=en)  
> 17. Banister Training Impulse Equation | Steven Lords Website, [https://stevenlord.uk/2018/04/19/banister-training-impulse-equation/](https://stevenlord.uk/2018/04/19/banister-training-impulse-equation/)  
> 18. The three-dimensional impulse-response model \- PMC, [https://pmc.ncbi.nlm.nih.gov/articles/PMC12880663/](https://pmc.ncbi.nlm.nih.gov/articles/PMC12880663/)  
> 19. How to Use Acute:Chronic Workload Ratio (ACWR) \- PoinT GO, [https://research.poin-t-go.com/en/how-to/how-to-use-acwr-workload-ratio](https://research.poin-t-go.com/en/how-to/how-to-use-acwr-workload-ratio)  
> 20. The Acute: Chronic Workload Ratio: A useful tool for monitoring, [https://pess.blog/2019/10/15/the-acute-chronic-workload-ratio-a-useful-tool-for-monitoring-training-load-alan-griffin/](https://pess.blog/2019/10/15/the-acute-chronic-workload-ratio-a-useful-tool-for-monitoring-training-load-alan-griffin/)  
> 21. Acute:chronic workload ratio and load management for team sports, [https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2026.1896651/full](https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2026.1896651/full)  
> 22. Acute:Chronic Workload Ratio \- Science for Sport, [https://www.scienceforsport.com/acutechronic-workload-ratio/](https://www.scienceforsport.com/acutechronic-workload-ratio/)  
> 23. Has the Acute:Chronic Workload Ratio Been Debunked?, [https://www.globalperformanceinsights.com/post/has-the-acute-chronic-workload-ratio-been-debunked](https://www.globalperformanceinsights.com/post/has-the-acute-chronic-workload-ratio-been-debunked)  
> 24. Acute:Chronic Workload Ratio: Conceptual Issues and Fundamental, [https://pubmed.ncbi.nlm.nih.gov/32502973/](https://pubmed.ncbi.nlm.nih.gov/32502973/)  
> 25. What Role Do Chronic Workloads Play in the Acute to ... \- PubMed, [https://pubmed.ncbi.nlm.nih.gov/33332011/](https://pubmed.ncbi.nlm.nih.gov/33332011/)  
> 26. How (and Why) to Cycle Your Exercise with Your Menstrual Cycle, [https://www.healthline.com/health/fitness/female-hormones-exercise](https://www.healthline.com/health/fitness/female-hormones-exercise)  
> 27. (PDF) The Effects of Menstrual Cycle Phase on Exercise, [https://www.researchgate.net/publication/342901039\_The\_Effects\_of\_Menstrual\_Cycle\_Phase\_on\_Exercise\_Performance\_in\_Eumenorrheic\_Women\_A\_Systematic\_Review\_and\_Meta-Analysis](https://www.researchgate.net/publication/342901039_The_Effects_of_Menstrual_Cycle_Phase_on_Exercise_Performance_in_Eumenorrheic_Women_A_Systematic_Review_and_Meta-Analysis)  
> 28. The Effects of Menstrual Cycle Phase on Exercise Performance in, [https://pubmed.ncbi.nlm.nih.gov/32661839/](https://pubmed.ncbi.nlm.nih.gov/32661839/)  
> 29. Menstrual Cycle and Training Planning: Physiological, [https://ctyeh.com/articles/14165?lang=en](https://ctyeh.com/articles/14165?lang=en)  
> 30. Menstrual Cycle Effects on Training & Performance \- Athletic Lab, [https://www.athleticlab.com/part-iii-menstrual-cycle-implications-on-training-periodization-and-performance-by-beatriz-fernandes/](https://www.athleticlab.com/part-iii-menstrual-cycle-implications-on-training-periodization-and-performance-by-beatriz-fernandes/)  
> 31. Menstrual cycle and exercise: how women can adapt their training to, [https://www.narayana-verlag.com/blog/menstrual-cycle-and-exercise-how-women-can-adapt-their-training-to-their-bodies](https://www.narayana-verlag.com/blog/menstrual-cycle-and-exercise-how-women-can-adapt-their-training-to-their-bodies)  
> 32. Menstrual cycle and exercise | TRIA Blog \- HealthPartners, [https://www.healthpartners.com/blog/how-tracking-your-period-can-help-improve-athletic-performance/](https://www.healthpartners.com/blog/how-tracking-your-period-can-help-improve-athletic-performance/)  
> 33. Stuart McGill Big 3: Chronic Back Pain Relief, [https://petersenpt.com/mcgill-big-3-exercises-chronic-back-pain-relief](https://petersenpt.com/mcgill-big-3-exercises-chronic-back-pain-relief)  
> 34. McGill Big 3 Core Stability Exercises | PDF \- Scribd, [https://www.scribd.com/document/627941431/McGill-Big-3-Intervention](https://www.scribd.com/document/627941431/McGill-Big-3-Intervention)  
> 35. The McGill Big 3: Exercises for Low Back Pain | BeFit, [https://befittrainingphysio.com/blog/low-back-pain-try-the-mcgill-big-3/](https://befittrainingphysio.com/blog/low-back-pain-try-the-mcgill-big-3/)  
> 36. Best exercises for lower back pain prevention \- Peterson Chiropractic, [https://www.petersonsportschiropractic.com/blog/1270866-best-exercises-for-lower-back-pain-prevention](https://www.petersonsportschiropractic.com/blog/1270866-best-exercises-for-lower-back-pain-prevention)  
> 37. percentage of lower limb arterial occlusion pressure at fixed values, [https://acikerisim.aksaray.edu.tr/items/321fb898-4ef1-4fa7-a676-d5c276f4486e](https://acikerisim.aksaray.edu.tr/items/321fb898-4ef1-4fa7-a676-d5c276f4486e)  
> 38. Everything you need to know about Blood Flow Restriction (BFR, [https://www.prohealthcareproducts.com/blog/everything-you-need-to-know-about-blood-flow-restriction-bfr-training/](https://www.prohealthcareproducts.com/blog/everything-you-need-to-know-about-blood-flow-restriction-bfr-training/)  
> 39. Blood flow restriction training guidelines | ASC, [https://www.ausport.gov.au/ais/position\_statements/blood-flow-restriction-training-guidelines](https://www.ausport.gov.au/ais/position_statements/blood-flow-restriction-training-guidelines)  
> 40. Validity and reliability of a wearable blood flow restriction training, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11191424/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11191424/)  
> 41. Blood Flow Restriction Exercise: Considerations of Methodology, [https://pmc.ncbi.nlm.nih.gov/articles/PMC6530612/](https://pmc.ncbi.nlm.nih.gov/articles/PMC6530612/)  
> 42. BFR Training: Benefits and Safety Considerations \- Fit Cuffs, [https://fitcuffs.com/blood-flow-restriction/bfr-safety/](https://fitcuffs.com/blood-flow-restriction/bfr-safety/)  
> 43. Training Readiness vs Body Battery: Which to Trust?, [https://www.shoulditrain.com/blog/garmin-training-readiness-vs-body-battery](https://www.shoulditrain.com/blog/garmin-training-readiness-vs-body-battery)  
> 44. Garmin Training Readiness \- Not Accurate \- Here's Why \- the5krunner, [https://the5krunner.com/2023/08/02/garmin-training-readiness-not-accurate-heres-why/](https://the5krunner.com/2023/08/02/garmin-training-readiness-not-accurate-heres-why/)  
> 45. The Ultimate Guide to TrainingPeaks for Coaches (2026), [https://www.trainingpeaks.com/blog/trainingpeaks-guide-for-coaches/](https://www.trainingpeaks.com/blog/trainingpeaks-guide-for-coaches/)  
> 46. Acute:Chronic Workload Ratio – Part 2 \- Gpexe, [https://www.gpexe.com/acutechronic-workload-ratio-part-2/](https://www.gpexe.com/acutechronic-workload-ratio-part-2/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAYCAYAAAAVibZIAAAAb0lEQVR4XmNgGAWjYFCAQnQBaoCFQKyKLkgpsAbibeiC1ADZQJyGLogMhIBYigy8FIjXQtkYoBOIl5OBTwLxPyCuZ6ASUAHivQyQ8KUK4ADiK0Asgy5BCUgB4mJ0QUrBfiBmQRekFEiiC4yCUQABAFjoFNtadlmVAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAYCAYAAAAcYhYyAAABFklEQVR4Xu3SoUtDURTH8YMKatGgQwcDo8EyEJsra4KI4GBpYctqsGgZFsuUoWEg2JSxokaTCtpkVaz+ARoFF4S57+XcPQ73Md0f8H7wgXfPue/yDveJJEkyfEaRR9qvx7CBxWjHELnEBb5QQRPbeMGB2TcwKzhBBr+4x7jvbeEH0349MCVkURA9ZNX0ir62aWoj5jmWVzwEtSd0MOXXV9iJukFm0UXV1OZFR9nHMk7xgRusm31R3Ozus89M7Rpt0ZtyIyzhE5OitxlLA984F335GUeYMHvKuDXrWN7w6J9TmDG9ftxvsBsW+5kTHeUwbAR5F73FHNaCntRED9nDQtCzuUMdx2HDxV2b0xKd+6/8+9Ml0fQAUK8tbaVTUsgAAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAcAAAAbCAYAAACwRpUzAAAAkklEQVR4XmNgGOTABYgXoQvCwFEgPo4uCAM4JXmA+DcQdyAL8gGxChDHAPF/IE4HYlUgZgVJZgHxTiB+xgDRCWKDsDRIEgZA9h1DFoABbiD+BcTt6BIg4MYAsc8dXQIE2hgg9oFcjAFAdp1E4s8DYhYY5wUQz4Gy04C4BCYBAhVA/B6IZwJxK7IEDIgy4LBzuAMAgKgZojrC66sAAAAASUVORK5CYII=>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAZCAYAAAArK+5dAAABTElEQVR4Xu3TvS8EQRjH8UfES0S8NCKXCImIgghBRHe14v4AUSCIKJRUKvGSaCh1QsKpLtdJuEKjIjqN2kui0YhQ4Dt5Zvce5+Lu4grF/pJPdp6Zyc7u7KxIlChRbAbRk9tJ6k27Q/LPKZhVbOMWC6Y/gTc0+voOT9nh4jKEtG8/YN+MHYneNMgxXlBh+gpmEgPox6evg7gFD009gitTl5RNvKPZ192iC86FM0T6sGvqknKDU1PPii7gFgqyhDFTF51KfGDd9O3gVbL77a5nqAlniIxjA72Yx7QZ+5EMkr5dhUvRRTt93wRmfNtlBTHRN3rEKO5FHzZv4rgW/ahuq6ZwjgsciB5je3qG/XURe6hFVzj6S9pQZ+oWtJs6Nyn5fvLKEvd3uxs34Fn0yauxbCf9Ja04wZboj7kmeszd25Yt7iAEW9lkB6L8r3wBdWsy7mG4k20AAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABMAAAAZCAYAAADTyxWqAAABP0lEQVR4Xu3UPyiFURjH8QeJS4pBDFjJTvkzKqOJklgo+TMobDZFFpNF2EwsbplYDOwUiuwGBilM4nt6nnud9zC85zXyq0+dP0/nvvec874ifzY1qA4HY7OKN3xgMZjLlAnRxbrCiSzZwgvKw4ksucNxOJglzaJ/cckba0C310+dUdHFelGKNeziAoNeXaps41X0WmygE9OiPzDm1aWK268r0UXbbawVM6gsFKVJk+gTPOEScyhJVERkRHSxHtENf8ROoiIim5K8Xwe4tfYw+q3tXrVxLIjuaZuNJ3KNI6+/hxNrH4oeShXO0IFa3GPIaoqpwDtmvbE+PIguWjhJd//2rV2GZzRaP5EW+b7h7gTrvf45pqztnu7Gm4vOqXy9DcuiBzSJumJFRAawjnmsIC+//FS5/c1ZO+oi/+fnfAKOcjSheZ8yJQAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABQAAAAZCAYAAAAxFw7TAAABTklEQVR4Xu2TPShGURjHH/IVMShZXjYpFpPyMUnJIotBIgODj8FAGZgMomwU8W4GWV6DiUJZLQqDLGYGi49F/E7PpXMeXnFMyq9+dc//eXruvefcK/IPlGKJDWOYx0d8wSlTi2ZIdGCTLcSyjveYbwuxXOG+DWOpEn3dGS+rxGZv/SP6RQe2Yi4u4CaeYo/X92028EH0k1nGRhwVvcmA1+fz5V67/TsXHVyXZLU4hkVvTR4jmMFFW3CkRJ/kDs9wAnOCjpBivMQuHAxLSp/owBbRQ7jFdNAR0o2HNvRZk/D72xF9AkcvdiTXjmk8Ft2eJcmyjxe456238Si53pXw33YDXDaMhV7+jgufcdzL2vFGdPBnJ3yNDTb0qZaPh+BOtsJkjnJ8kiyvGkMbntjwN0ziig1jyMMy3MJOU4tiDlfxAAtMLYp6nMUaW/hbvAJafDbez7S5MgAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAZCAYAAAA8CX6UAAAA40lEQVR4XmNgGAWjgPpADoiVgVgFCSsBMQ+yInzACIgvAvF/HHgxQiluIA3El4E4E4htgLgCiNcDsS0QWwOxJRDzw1XjAWFArI3EnwrEaUh8sgAjED8BYlN0CVKBCRD/AWIOdAlSQTMDJLywAXcgrmWAhKMTmhwGuATEi9AFgaAOiNsYIF5fCMSrUaVRATcQfwPiFDRxDag4J5QPMigXIY0dyDBAbEUG1UC8D4n/AIj1kPhEg3wg7oeyQQZ8AGJFII6CqyASgFw5H4jzGCCJ9RAQT2CgIGYFoTTI6+zIEqOAOAAA0HkhylAf8MEAAAAASUVORK5CYII=>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABMAAAAZCAYAAADTyxWqAAAA/klEQVR4Xu3QMUsCYRjA8TeNEAyCaEsULWgIHEIJ0T6Ag5Pg4iSI4DeoOZxcWmwIRLKhsdHF7yDaF2hwkuZAEOp/voe+PtydeEMg3B9+wz3PC3f3KhUU9P/FcYFLQwrH5qFt3WCMXxdv66PeneMTTRRwjw/cIY8cTlandSGExWxZBdfGcwcN41l2hXeMcCh2Gx1giqxcGL2iime5kGWwQEQu7Kwv+cGZXDj1qPT9OVVEF3M8Kf1izyboy6Gddek1DJT+cutKXIsq/Qt1uTBqoyWHbsWU9xuHKMuh376RlEM/JTCTQz+dKv17PbnYtTS+8ILbzdXuHeEBJbnYn/4A3nQkABT09n4AAAAASUVORK5CYII=>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEwAAAAaCAYAAAAdQLrBAAACZklEQVR4Xu2YTUhUURTHT5bSJwhhQV8SBEGLMMK0iBrCKCgo2gRRYYSUi0AhIilEKkKQPkWDWukqiApaVyq6aBUYtAlatC77gCiCsv6H85y58/e9cSZmnO7r/eAH751z30Pv3HvevVckfiyCJ2AbXE25BGIOvAc3wuPwO9yQ1SIhi+3wB1we3D+FDzPp4lMN53HQIxbDo2IjTdHOGsiki08X/Ap7Ke4jK+AHuJUTxaYP/oYNnPCIufAx3MeJUrBJrMN8HmU9sCm43uYmSsVr+F78rGfn4WmxH75RZumH7xAbZfs58Y+TEvu7XbucfMlYAyfhfU4kRDMKv8ElnAjhLhyJcBgOBT6Hz2CzPhQndol9knVIN2enEpi98B2sF1s162q5XHA9mi3z5gD8JJk12CP4C65MtwhnM9xdgOvsMb85LDaiDjmxg2I9ftaJhXEKXixAnfJecwT+hO0UrxSrZa8oXg72wAfwJdzpxM/BMbEPyhYnni91UuDyqQp+hrc5EXBVbJSlKF4O9IzrBXxC8UG4lGJTRG3x1os9p4v0m5SbkWWS2eEzGtcaVcOJMnAD7hCrq2uDmO5GbqVbTOcSBwjdO+t7Y0cFvBZcj4vtFxWdhseC6zAuc4CIbYdprdFTVKUFTsAFYjVs1VSjEK5wgNAOK3hK+oDWr9rgeiH8CE/K9M11Cl5wHKL7M+mWRmw7jOuUTkmdmtcprmdh8x276V4/ci7aYfxu79F/kkeSFn0t/rokykU+UzJqheAlunh+C7/AVsrpmb0eReciqsP0RKZfbFnxBt6Rmd/1X9DJgYTcRK0v/4o/dIePsy7xECIAAAAASUVORK5CYII=>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAZCAYAAAAFbs/PAAAAwElEQVR4XmNgGPRAAIhZ0AXxgQYg/gLEk9HE8YKpQPwfiM3RJXABQwaIBpJsuQrErxlI8E8lA8QWH3QJXEAOiP8B8Qp0CXzgMBB/A2JedAlswAmI3zBAnJWAKoUJPID4IRCbAvFPIN6DKo0K/IH4PQMiDtYB8V8gloarQALhDBATg5DEAhggzipBEgODKCD+A8SFaOKsDBC/XEIWZAPiD0A8CVkQCbQxQGxxQBYUA2JGZAEkABI3BmJRdIlRQDUAANZuIDNEgo4WAAAAAElFTkSuQmCC>