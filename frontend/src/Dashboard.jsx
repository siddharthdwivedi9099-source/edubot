import { useEffect, useState } from "react";
import { api } from "./api.js";

// ─────────────────────────────────────────────────────────────────────────────
// Per-role dashboard tiles. Clicking a tile seeds the chat with a question.
// ─────────────────────────────────────────────────────────────────────────────

const FIRST_NAME = (full) =>
  (full || "there").split(" ")[0];

const ROLE_HEADLINE = {
  student: (n) => (
    <>Hello, <em>{n}</em>.<br/>What would you like to know?</>
  ),
  parent: (n) => (
    <>Welcome back, <em>{n}</em>.<br/>Here's how things are at school.</>
  ),
  teacher: (n) => (
    <>Good day, <em>{n}</em>.<br/>Your classroom, summarised.</>
  ),
  principal: (n) => (
    <>Welcome, <em>{n}</em>.<br/>Your school at a glance.</>
  ),
  admin: (n) => (
    <>Hello, <em>{n}</em>.<br/>Operations dashboard.</>
  ),
  super_admin: (n) => (
    <>Welcome, <em>{n}</em>.<br/>The group, all in one place.</>
  ),
};

const ROLE_LEAD = {
  student:    "Track what's due, how you're doing, and what's coming up.",
  parent:     "Your child's attendance, grades, fees, and school events — together.",
  teacher:    "Your classes, assignments, attendance, and student watch-list.",
  principal:  "Academic outcomes, finances, and operations across your school.",
  admin:      "Admissions, fees, transport, and operational activity.",
  super_admin:"Cross-school KPIs and benchmarking across all 20 campuses.",
};

const TILES = {
  student: [
    { icon: "📅", title: "My attendance",        desc: "How many days have I been present this term?",
      q: "Show my attendance for this term." },
    { icon: "📊", title: "My recent marks",       desc: "Latest test and exam scores.",
      q: "What are my marks in the latest exams?" },
    { icon: "📝", title: "My pending assignments",desc: "What's due, what's submitted.",
      q: "List my pending assignments." },
    { icon: "🎓", title: "My progress report",    desc: "CBSE-style term report card.",
      q: "Show my progress report for Term 1." },
    { icon: "⏰", title: "My class today",        desc: "Today's timetable and teachers.",
      q: "What's my schedule today?" },
    { icon: "🏆", title: "Upcoming events",       desc: "Sports day, exhibitions, festivals.",
      q: "What school events are coming up?" },
    { icon: "💸", title: "My fee status",         desc: "Outstanding dues and recent payments.",
      q: "What's my current fee status?" },
    { icon: "📚", title: "Study help",            desc: "CBSE concepts, tips, exam prep.",
      q: "Help me prepare for my Mathematics exam." },
  ],
  parent: [
    { icon: "👶", title: "My child's attendance",  desc: "Daily presence, late marks, leaves.",
      q: "Show my child's attendance this month." },
    { icon: "📊", title: "My child's marks",       desc: "All subjects, all terms.",
      q: "What are my child's recent marks?" },
    { icon: "💸", title: "Fees & payments",        desc: "Dues, history, receipts.",
      q: "What is my child's current fee status?" },
    { icon: "📝", title: "Pending assignments",    desc: "What hasn't been submitted yet.",
      q: "What assignments has my child not submitted?" },
    { icon: "🎓", title: "Progress report",        desc: "Term report cards.",
      q: "Show my child's latest progress report." },
    { icon: "⚖️", title: "Discipline record",     desc: "Incidents, warnings, resolutions.",
      q: "Has my child had any discipline incidents this year?" },
    { icon: "📅", title: "School events",          desc: "PTM, sports day, holidays.",
      q: "When is the next Parent-Teacher Meeting?" },
    { icon: "🏫", title: "School policies",        desc: "Fee, transport, leave, uniform.",
      q: "What is the school's leave policy?" },
  ],
  teacher: [
    { icon: "📅", title: "My classes today",       desc: "Today's timetable and rooms.",
      q: "Show my schedule today." },
    { icon: "🎯", title: "Class attendance",       desc: "Today's presence by class.",
      q: "Show today's attendance for my classes." },
    { icon: "📝", title: "Submissions to grade",   desc: "What's submitted but not graded.",
      q: "Which assignments do I still need to grade?" },
    { icon: "📊", title: "Class performance",      desc: "Term averages, top & bottom.",
      q: "Show class performance summary for my homeroom." },
    { icon: "⚠️", title: "At-risk students",      desc: "GPA < 2.5 or attendance < 75%.",
      q: "Which students in my class are at academic risk?" },
    { icon: "📋", title: "Discipline this week",   desc: "Incidents you've reported or witnessed.",
      q: "Show discipline incidents in my class this week." },
    { icon: "🏆", title: "Upcoming events",        desc: "What's on the school calendar.",
      q: "What school events are coming up?" },
    { icon: "📚", title: "Teaching resources",     desc: "Marking guides, lesson plans.",
      q: "Show me the marking guidelines for assignments." },
  ],
  principal: [
    { icon: "📊", title: "School performance",     desc: "Term-wise averages by grade.",
      q: "Show this term's class-wise performance for the school." },
    { icon: "🎯", title: "Attendance summary",     desc: "Daily and term attendance rates.",
      q: "What is the school's overall attendance rate this term?" },
    { icon: "💰", title: "Fee collection",         desc: "Collected vs outstanding.",
      q: "Show fee collection status across the school." },
    { icon: "⚠️", title: "At-risk students",      desc: "School-wide watch-list.",
      q: "How many students across the school are academically at risk?" },
    { icon: "👩‍🏫", title: "Teacher performance", desc: "Ratings, attendance, workload.",
      q: "Show teacher performance ratings for my school." },
    { icon: "📋", title: "Discipline trends",      desc: "Categories and frequency.",
      q: "What types of discipline incidents are most common this term?" },
    { icon: "🏆", title: "Events calendar",        desc: "Past, present, upcoming.",
      q: "List the upcoming school events." },
    { icon: "📈", title: "10-year history",        desc: "Long-term trends.",
      q: "Show enrolment trends over the last 10 years." },
  ],
  admin: [
    { icon: "🚪", title: "Admissions",             desc: "New, pending, completed.",
      q: "How many new admissions this academic year?" },
    { icon: "💰", title: "Fee collection",         desc: "Collected, outstanding, defaulters.",
      q: "Show today's fee collection summary." },
    { icon: "🚌", title: "Transport",              desc: "Routes, occupancy, payments.",
      q: "Show transport fee collection status." },
    { icon: "🧾", title: "Receipts",               desc: "Recent payment receipts.",
      q: "Show today's payment receipts." },
    { icon: "📅", title: "Operations calendar",    desc: "Events to plan for.",
      q: "What events are scheduled this month?" },
    { icon: "📋", title: "Defaulter list",         desc: "Outstanding > 30 days.",
      q: "Who are the fee defaulters this term?" },
    { icon: "📜", title: "Documentation",          desc: "TCs, certificates, forms.",
      q: "What documents are pending issuance?" },
    { icon: "🏫", title: "Capacity & roster",      desc: "Class strength by section.",
      q: "Show class strengths across all grades." },
  ],
  super_admin: [
    { icon: "🌐", title: "Group overview",         desc: "All 20 schools at a glance.",
      q: "Show enrolment by school for the group." },
    { icon: "📊", title: "Academic benchmarking",  desc: "Cross-school performance.",
      q: "Compare academic performance across the 20 schools." },
    { icon: "💰", title: "Group financials",       desc: "Fee collection by school.",
      q: "Show fee collection rate by school." },
    { icon: "🎯", title: "Attendance comparison",  desc: "Best and worst performing.",
      q: "Which schools have the highest and lowest attendance rates?" },
    { icon: "👩‍🏫", title: "Staff distribution",  desc: "Teachers, ratios, vacancies.",
      q: "How is teacher headcount distributed across schools?" },
    { icon: "⚠️", title: "Risk dashboard",        desc: "At-risk students by school.",
      q: "Which schools have the most academically at-risk students?" },
    { icon: "🏆", title: "Events across schools",  desc: "What's happening this month.",
      q: "What events are happening across the group this month?" },
    { icon: "📈", title: "10-year growth",         desc: "Historical enrolment & financials.",
      q: "Show 10-year enrolment growth across the group." },
  ],
};

// ─────────────────────────────────────────────────────────────────────────────
// Stat strip — fed by /erp/query for principal/super_admin/admin
// ─────────────────────────────────────────────────────────────────────────────

const STAT_QUERIES = {
  principal: [
    { eyebrow: "Students enrolled", q: "How many active students are in the school?" },
    { eyebrow: "Teachers on staff", q: "How many active teachers are in the school?" },
    { eyebrow: "Avg attendance",    q: "What is the average attendance percentage this term?" },
    { eyebrow: "Open discipline",   q: "How many discipline incidents this academic year?" },
  ],
  admin: [
    { eyebrow: "Students enrolled", q: "How many active students are in the school?" },
    { eyebrow: "Fee defaulters",    q: "How many students have fee_outstanding > 0 in the school?" },
    { eyebrow: "On transport",      q: "How many students opted for transport in the school?" },
  ],
  super_admin: [
    { eyebrow: "Schools",           q: "How many schools are in the group?" },
    { eyebrow: "Total students",    q: "How many active students across the group?" },
    { eyebrow: "Total teachers",    q: "How many active teachers across the group?" },
    { eyebrow: "Total events",      q: "How many events are recorded across the group in total?" },
  ],
  teacher: [
    { eyebrow: "My classes",        q: "How many classes am I assigned to?" },
    { eyebrow: "Submissions to grade", q: "How many assignments are submitted but not graded by me?" },
  ],
  student: [],   // students get richer narrative tiles, not stats
  parent: [],
};

// ─────────────────────────────────────────────────────────────────────────────

export default function Dashboard({ user, onAskQuestion }) {
  const tiles = TILES[user.role] || TILES.student;
  const headline = ROLE_HEADLINE[user.role] || ROLE_HEADLINE.student;
  const lead = ROLE_LEAD[user.role] || ROLE_LEAD.student;
  const stats = STAT_QUERIES[user.role] || [];

  return (
    <>
      <section className="dash-hero">
        <div>
          <h1 className="display">{headline(FIRST_NAME(user.full_name))}</h1>
          <p className="lead" style={{ marginTop: 12 }}>{lead}</p>
        </div>
      </section>

      {stats.length > 0 && <StatStrip stats={stats} />}

      <section className="dash-section">
        <div className="dash-section-header">
          <h2>What can I help with?</h2>
          <span className="sub">Tap a tile to ask EduBot</span>
        </div>
        <div className="tile-grid">
          {tiles.map((t, i) => (
            <button
              key={i}
              className="tile"
              onClick={() => onAskQuestion(t.q)}
              type="button"
            >
              <div className="tile-icon">{t.icon}</div>
              <div className="tile-title">{t.title}</div>
              <div className="tile-desc">{t.desc}</div>
              <span className="tile-arrow">→</span>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}

function StatStrip({ stats }) {
  const [data, setData] = useState(stats.map(() => ({ loading: true })));

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      stats.map(async (s) => {
        try {
          const res = await api.erpQuery(s.q);
          // Pull a single number out of res.rows if possible
          let num = "—";
          if (res.rows?.length) {
            const r = res.rows[0];
            const v = Object.values(r)[0];
            num = typeof v === "number"
              ? v.toLocaleString("en-IN")
              : (v == null ? "—" : String(v));
          }
          return { num, summary: res.summary };
        } catch (e) {
          return { num: "—", error: e.message };
        }
      })
    ).then((vals) => {
      if (!cancelled) setData(vals);
    });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="stat-strip">
      {stats.map((s, i) => (
        <div key={i} className="stat-card">
          <div className="stat-eyebrow">{s.eyebrow}</div>
          <div className="stat-num">
            {data[i]?.loading ? "…" : data[i]?.num ?? "—"}
          </div>
        </div>
      ))}
    </div>
  );
}
