"""Phase E — golden conversation bank (200+ real user question types).

Each entry defines expected routing (intent + skill) for regression testing.
Messages are phrasing variants athletes actually use — not prompt templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.coach_reply_eval import GroundingEvalCase
from app.services.coach_intent import (
    CLINICAL_VETO,
    DAY_ADJUST,
    GENERAL_CHAT,
    OFF_TOPIC,
    SCHEDULE_UPDATE,
    SCIENCE_LOOKUP,
    WEEK_PLAN_REVIEW,
    WEEK_REVIEW,
    WORKOUT_AUDIT,
)
from app.services.coach_skills import (
    SKILL_ADJUST_DAY,
    SKILL_CLINICAL,
    SKILL_EXPLAIN_METRIC,
    SKILL_GENERAL_CHAT,
    SKILL_GO_DEEPER,
    SKILL_OFF_TOPIC,
    SKILL_REBUILD_WEEK,
    SKILL_REVIEW_SESSION,
    SKILL_SUPPORT_CHAT,
    SKILL_VALIDATE_PLAN,
    SKILL_WEEK_DEBRIEF,
    SKILL_WEEK_PLAN_REVIEW,
)


@dataclass(frozen=True)
class GoldenRoutingCase:
    case_id: str
    message: str
    category: str
    expected_skill: str
    expected_intent: str | None = None
    acceptable_skills: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)


def _cases(
    category: str,
    skill: str,
    intent: str | None,
    messages: list[str],
    *,
    acceptable_skills: tuple[str, ...] = (),
) -> list[GoldenRoutingCase]:
    allowed = acceptable_skills or (skill,)
    return [
        GoldenRoutingCase(
            case_id=f"{category}_{index:03d}",
            message=message,
            category=category,
            expected_skill=skill,
            expected_intent=intent,
            acceptable_skills=allowed,
        )
        for index, message in enumerate(messages, start=1)
    ]


_VALIDATE_PLAN = _cases(
    "validate_plan",
    SKILL_VALIDATE_PLAN,
    GENERAL_CHAT,
    [
        "Should I use this Fri–Sun plan?",
        "Should I do this weekend schedule or rest?",
        "Does this plan make sense for me?",
        "Is this schedule ok with my HRV being low?",
        "Would this work for taper week?",
        "Can I do this stack: easy Fri, long Sat, rest Sun?",
        "Tell me should I stick with this Fri–Sun idea",
        "What do you think of my Fri long run + Sat bike plan?",
        "Good idea to do intervals tomorrow and long run Sunday?",
        "Ok to do a hard bike session Friday then race Saturday?",
        "I'm thinking Fri easy, Sat long run 90 min, Sun rest — thoughts?",
        "My plan is Mon rest Tue tempo Wed easy — should I go with it?",
        "Should I go with this DIY week ending in a half marathon?",
        "Would this work: keep volume, drop the second hard day?",
        "Is this plan ok if I missed Tuesday?",
        "Should I do this or play it safer?",
        "Can I do this plan while traveling Sunday?",
        (
            "Hello coach So tell me now that's it 3 pm i will do endurance ride at 4pm 1 hr ride "
            "and after 30 mins to 60 mins I'll do Upper body + core And tomorrow I'll do Long ride "
            "and mobility in evening and on sunday I'll be doing long easy run no matter what, got it. "
            "so tell me how can i plan it, as my rest week starts from monday so before that i want to "
            "finish the base week perfectly as per my plan so tell me is there any problem in my plan "
            "which i told you right now? tell me my plans Pros and cons."
        ),
    ],
    acceptable_skills=(SKILL_VALIDATE_PLAN, SKILL_GENERAL_CHAT, SKILL_ADJUST_DAY),
)

_SUPPORT_CHAT = _cases(
    "support_chat",
    SKILL_SUPPORT_CHAT,
    GENERAL_CHAT,
    [
        "I missed two sessions — what now?",
        "I feel guilty about skipping yesterday",
        "Life got in the way this week, feeling defeated",
        "I failed to hit my workouts — am I ruined?",
        "Rough day, couldn't make the run — feeling guilty",
        "I skipped training for a bike fit — help me reset",
        "Not motivated after a bad week",
        "I cut it short today and feel like I failed",
        "Overwhelmed with work and missed three runs",
        "Traveling by train — missed Saturday long run, anxious",
        "Jet lag and I missed Monday — how do I recover mentally?",
        "Busy week, didn't train much, feeling discouraged",
        "I have a cold but it's not terrible — just off",
        "Under the weather and missed two days",
        "Burnt out and can't keep up with the plan",
        "Lost motivation after missing the long run",
        "Stress at work, rough patch — missed two sessions",
        "Missed workouts for travel — feeling guilty",
    ],
    acceptable_skills=(SKILL_SUPPORT_CHAT, SKILL_GENERAL_CHAT, SKILL_ADJUST_DAY),
)

_EXPLAIN_METRIC = _cases(
    "explain_metric",
    SKILL_EXPLAIN_METRIC,
    None,
    [
        "Why is my HRV low?",
        "Why has my HRV dropped this week?",
        "What's wrong with my sleep score?",
        "Why is my ACWR so high?",
        "Why is my readiness score low today?",
        "Why is my resting heart rate elevated?",
        "What is ACWR?",
        "Explain HRV in plain language",
        "What does training load ratio mean?",
        "Why does ACWR matter for my training this week?",
        "What is polarized training?",
        "Explain lactate threshold simply",
        "What is FTP on the bike?",
        "How does HRV relate to recovery?",
        "What is cardiac drift?",
        "Explain zone 2 training",
        "What is sweet spot training?",
        "Why is my sleep score low after a hard week?",
        "What is TSS?",
        "Explain training stress balance",
    ],
    acceptable_skills=(SKILL_EXPLAIN_METRIC, SKILL_GENERAL_CHAT, SKILL_ADJUST_DAY),
)

_ADJUST_DAY = _cases(
    "adjust_day",
    SKILL_ADJUST_DAY,
    DAY_ADJUST,
    [
        "HRV is low, should I still do intervals today?",
        "Skip today's quality session?",
        "ACWR is high, skip today's quality",
        "Readiness is bad — swap today for easy?",
        "Stress is high this morning, what should I do today?",
        "Should I rest today instead of the planned tempo?",
        "Feeling flat — adjust today only",
        "Can I swap today's run for yoga?",
        "Today's workout feels too hard — easy day instead?",
        "Low sleep score — still do the hard session today?",
        "Knee feels tight but not sharp — modify today?",
        "Should I push through today's intervals?",
        "Replace today's bike with a walk?",
        "Not recovered — change today not the whole week",
        "How should I adjust today with poor HRV?",
    ],
    acceptable_skills=(
        SKILL_ADJUST_DAY,
        SKILL_GENERAL_CHAT,
        SKILL_SUPPORT_CHAT,
        SKILL_REVIEW_SESSION,
    ),
)

_REVIEW_SESSION = _cases(
    "review_session",
    SKILL_REVIEW_SESSION,
    WORKOUT_AUDIT,
    [
        "How was today's session?",
        "Analyse this ride",
        "How was my run this morning?",
        "Autopsy my last ride",
        "How was yoga today?",
        "How was the long run?",
        "Break down today's session",
        "How was my swim?",
        "Rate today's workout",
        "You got it wrong coach — that wasn't an easy day",
        "How did I do today?",
        "Session review — how was the ride?",
        "Tell me how today's workout went",
        "Debrief today's run",
        "How was today's bike session?",
    ],
    acceptable_skills=(SKILL_REVIEW_SESSION, SKILL_GENERAL_CHAT),
)

_REBUILD_WEEK = _cases(
    "rebuild_week",
    SKILL_REBUILD_WEEK,
    SCHEDULE_UPDATE,
    [
        "Plan my week around my lower back",
        "How should I adjust this week?",
        "Update my schedule for this week",
        "Plan my this week again keep the schedule same",
        "I want Mon rest Tue bike Wed run Thu easy Fri intervals",
        "Schedule my week with travel on Thursday",
        "Plan the week — 5 days, one quality session",
        "Give me a fresh week starting Monday",
        "Plan my week with yoga on Wednesday",
        "Adjust this week's plan — add a long run Sunday",
        "Build a recovery week for me",
        "Plan my week around a race on Saturday",
        "Schedule update: drop Friday intervals",
        "Plan my week with strength twice",
        "Replan with my new FTP and LTHR",
        "Plan my week",
        "Build my training week",
        "Update this week's calendar",
    ],
    acceptable_skills=(SKILL_REBUILD_WEEK, SKILL_GENERAL_CHAT),
)

_WEEK_DEBRIEF = _cases(
    "week_debrief",
    SKILL_WEEK_DEBRIEF,
    WEEK_REVIEW,
    [
        "How did I do this week?",
        "How was my week?",
        "Recap last week",
        "Grade my week",
        "Look at my week",
        "Week in review — how did it go?",
        "Done with the week — debrief me",
        "Review my week coach",
        "How did training go this week?",
        "Summarize my week",
        "Take a look at my week",
        "Weekly debrief please",
        "How was last week overall?",
        "Recap the week — wins and misses",
        "Finished the week — how did I do?",
    ],
    acceptable_skills=(SKILL_WEEK_DEBRIEF, SKILL_GENERAL_CHAT),
)

_WEEK_PLAN_REVIEW = _cases(
    "week_plan_review",
    SKILL_WEEK_PLAN_REVIEW,
    WEEK_PLAN_REVIEW,
    [
        "Review my proposed week before I commit",
        "Does this week structure look right before I save?",
        "Feedback on my week plan draft",
        "Check my week outline before scheduling",
        "Peer review my training week idea",
        "Review-only: is this week balanced?",
        "Look at my week plan — no save yet",
        "Sanity check my week before I commit",
        "Week plan review — too much intensity?",
        "Review my season week sketch",
    ],
    acceptable_skills=(
        SKILL_WEEK_PLAN_REVIEW,
        SKILL_GENERAL_CHAT,
        SKILL_REBUILD_WEEK,
        SKILL_WEEK_DEBRIEF,
        SKILL_EXPLAIN_METRIC,
    ),
)

_GO_DEEPER = _cases(
    "go_deeper",
    SKILL_GO_DEEPER,
    GENERAL_CHAT,
    [
        "Explain why in plain language — max 3 bullets, one watch number, no week table",
        "Quick follow-up only: why that watch number? No week table",
        "Go deeper on that answer — plain language, max 3 bullets",
        "Explain why you said that — quick follow-up only, watch number",
        "Follow up: why easy days matter here — no lecture",
        "Quick follow-up only on your last point — max 3 bullets",
        "Plain language why — one watch number, no week table",
        "Explain why briefly — follow-up only",
    ],
    acceptable_skills=(SKILL_GO_DEEPER, SKILL_GENERAL_CHAT, SKILL_EXPLAIN_METRIC),
)

_GENERAL_CHAT = _cases(
    "general_chat",
    SKILL_GENERAL_CHAT,
    GENERAL_CHAT,
    [
        "How easy should my easy sessions feel?",
        "Tips for pacing a half marathon?",
        "How should I fuel before a long run?",
        "Should I run doubles this block?",
        "How do I build consistency?",
        "What's a good warm-up before intervals?",
        "How long should my long run be?",
        "When should I add a second hard day?",
        "How do I handle heat in summer training?",
        "Best way to recover after a hard week?",
        "How should I structure rest days?",
        "Advice for first-time marathon training?",
        "How hard should threshold feel?",
        "Should I cross-train on rest days?",
        "How to progress weekly mileage safely?",
        "What should I focus on this month?",
        "How do I know if I'm overtraining?",
        "Tips for running in the rain?",
        "How should I breathe on easy runs?",
        "What cadence should I aim for?",
    ],
    acceptable_skills=(SKILL_GENERAL_CHAT, SKILL_EXPLAIN_METRIC, SKILL_REBUILD_WEEK),
)

_CLINICAL = _cases(
    "clinical",
    SKILL_CLINICAL,
    CLINICAL_VETO,
    [
        "Sharp pain in my knee when I run",
        "Achilles tendon hurts after yesterday",
        "Chest pain during intervals",
        "I think I tore something in my calf",
        "Stabbing pain in my hip",
        "Doctor said stress fracture — can I train?",
        "Sharp shin pain — should I run tomorrow?",
        "My back spasms when I deadlift",
        "Numbness in my foot after long runs",
        "ACL recovery — when can I run?",
        "Painful pop in my knee",
        "Diagnosed with plantar fasciitis — plan?",
    ],
    acceptable_skills=(SKILL_CLINICAL, SKILL_GENERAL_CHAT, SKILL_ADJUST_DAY),
)

_OFF_TOPIC = _cases(
    "off_topic",
    SKILL_OFF_TOPIC,
    OFF_TOPIC,
    [
        "What's the weather tomorrow?",
        "Write me a Python script",
        "Who won the election?",
        "Recommend a restaurant nearby",
        "Help with my taxes",
        "What's the capital of France?",
        "Tell me a joke about cats",
        "Book me a flight",
        "How do I fix my WiFi?",
        "What's the stock price of Apple?",
    ],
    acceptable_skills=(SKILL_OFF_TOPIC, SKILL_GENERAL_CHAT, SKILL_EXPLAIN_METRIC),
)

_TAPER_RACE = _cases(
    "taper_race",
    SKILL_GENERAL_CHAT,
    GENERAL_CHAT,
    [
        "How should I taper this week before my race?",
        "Race week — drop volume or intensity?",
        "Three days out from a half — what should I do?",
        "Pre-race nerves — normal?",
        "Should I run the day before a 5K?",
        "Marathon week plan — how much to cut?",
        "Taper madness — is this normal?",
        "Race morning routine tips?",
        "How fresh should I feel on race day?",
        "Can I do a short shakeout run Friday before Sunday race?",
        "Peak week vs taper — what's the difference?",
        "Should I carb load two days out?",
        "Race week sleep is bad — am I screwed?",
        "Strides during taper week?",
        "How to handle a B-race mid block?",
    ],
    acceptable_skills=(SKILL_GENERAL_CHAT, SKILL_REBUILD_WEEK, SKILL_EXPLAIN_METRIC),
)

_TRAVEL = _cases(
    "travel",
    SKILL_SUPPORT_CHAT,
    GENERAL_CHAT,
    [
        "Traveling next week — missed two runs, stressed",
        "Airport day — how do I salvage training?",
        "Time zone change ruined my sleep and I missed Monday",
        "Hotel gym only — rough week ahead",
        "Train ride all day Sunday — missed long run, anxious",
        "Business trip — busy and couldn't train",
        "Packing for travel — nervous about missing workouts",
        "Jet lag and missed sessions — help",
        "Travel fatigue — missed three days",
        "Away from home — stressed about falling behind",
        "Conference week — rough schedule, missed training",
        "Vacation without bike — feeling guilty",
        "Long flight then race — bad combo?",
        "Travel stress and missed quality session",
        "Can only run on treadmill while traveling — missed outdoor long run",
    ],
    acceptable_skills=(
        SKILL_SUPPORT_CHAT,
        SKILL_GENERAL_CHAT,
        SKILL_ADJUST_DAY,
        SKILL_REBUILD_WEEK,
    ),
)

GOLDEN_ROUTING_CASES: list[GoldenRoutingCase] = (
    _VALIDATE_PLAN
    + _SUPPORT_CHAT
    + _EXPLAIN_METRIC
    + _ADJUST_DAY
    + _REVIEW_SESSION
    + _REBUILD_WEEK
    + _WEEK_DEBRIEF
    + _WEEK_PLAN_REVIEW
    + _GO_DEEPER
    + _GENERAL_CHAT
    + _CLINICAL
    + _OFF_TOPIC
    + _TAPER_RACE
    + _TRAVEL
)

# Quality-reply cases (subset with reply expectations for mechanical scoring)
QUALITY_REPLY_CASE_IDS = frozenset(
    {
        "validate_plan_001",
        "validate_plan_018",
        "support_chat_001",
        "explain_metric_010",
        "rebuild_week_001",
        "general_chat_001",
    }
)

WEEKEND_BASE_WEEK_MESSAGE = _VALIDATE_PLAN[-1].message

APPLY_REMAINING_WEEK_MESSAGE = (
    "So update my remaining week as per new plan that we just discuussed right now."
)

NO_PROS_PLAN_MESSAGE = (
    "Hello coach So tell me now that's it 3 pm i will do endurance ride at 4pm 1 hr ride "
    "and after 30 mins to 60 mins I'll do Upper body + core And tomorrow I'll do Long ride "
    "and mobility in evening and on sunday I'll be doing long easy run no matter what, got it. "
    "so tell me how can i plan it, as my rest week starts from monday so before that i want to "
    "finish the base week perfectly as per my plan so tell me is there any problem in my plan "
    "which i told you right now?"
)

GROUNDING_EVAL_CASES: list[GroundingEvalCase] = [
    GroundingEvalCase(
        case_id="weekend_plan_no_memory_bleed",
        message=WEEKEND_BASE_WEEK_MESSAGE,
        description="Fri–Sun stack before rest week — must not invent bike fit/travel/Kolhapur",
        forbidden_patterns=(
            r"\bbike fit\b",
            r"\bkolhapur\b",
            r"\b(by train|on the train|train ride|traveling by train)\b",
            r"\btake a deep breath\b.*\bbike fit\b",
        ),
        required_patterns=(
            r"coach's rule",
            r"(pros|cons|bottom line)",
            r"(friday|saturday|sunday|rest week|recovery week|deload)",
        ),
    ),
    GroundingEvalCase(
        case_id="weekend_plan_no_pros_unless_asked",
        message=NO_PROS_PLAN_MESSAGE,
        description="Plan validation without pros/cons ask — template must not include Pros/Cons",
        forbidden_patterns=(r"\*\*Pros\*\*", r"\*\*Cons\*\*"),
        required_patterns=(r"coach's rule", r"bottom line"),
    ),
]
