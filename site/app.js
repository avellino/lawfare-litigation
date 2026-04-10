// ═══════════════════════════════════════════════════════
// Unified Legal Tracker — Main Application
// ═══════════════════════════════════════════════════════

let DATA = null;

// ── Color maps ──
const APPOINTER_COLORS = {
    "Joe Biden": "#3b82f6", "Barack Obama": "#22d3ee", "Bill Clinton": "#a78bfa",
    "George W. Bush": "#f87171", "Donald Trump": "#fb923c", "Ronald Reagan": "#f472b6",
    "George H.W. Bush": "#e879f9", "Jimmy Carter": "#34d399",
};
const VIOLATION_COLORS = {
    "Removal/Deportation Despite Order": "#ef4444", "Transfer Despite Order": "#f97316",
    "Failure to Return Detainee": "#f59e0b", "Failure to Timely Release": "#eab308",
    "Failure to Provide Detainee Medication": "#84cc16", "Imposed Conditions in Violation of Order": "#22c55e",
    "Failure to Return Property": "#14b8a6", "Failure to Provide Bond Hearing": "#06b6d4",
    "Failure to Produce Detainee": "#3b82f6", "Failure to Produce Evidence": "#6366f1",
    "Misrepresentation to the Court": "#8b5cf6", "Failure to Coordinate with Counsel": "#a855f7",
    "Failure to File": "#64748b", "Miscellaneous": "#475569",
};
const STATUS_COLORS = {
    "Pending / Filed": "#636EFA", "Injunction / TRO Granted": "#00CC96",
    "Injunction / TRO Denied": "#EF553B", "Stayed": "#FFA15A", "Stay Denied": "#FF6692",
    "On Appeal": "#AB63FA", "Appellate Decision": "#19D3F3", "Dismissed / Terminated": "#B6E880",
    "Summary Judgment": "#FECB52", "Procedural": "#72B7B2", "Other": "#999999",
};

function appointerColor(n) { return APPOINTER_COLORS[n] || "#6b7280"; }
function violationColor(n) { return VIOLATION_COLORS[n] || "#6b7280"; }

// Court URL → display name
const COURT_NAMES = {"dcd":"D.C.","cadc":"D.C. Cir.","mad":"D. Mass.","mdd":"D. Md.","ca9":"9th Cir.","nysd":"S.D.N.Y.","cand":"N.D. Cal.","ca1":"1st Cir.","rid":"D.R.I.","ca4":"4th Cir.","ilnd":"N.D. Ill.","wawd":"W.D. Wash.","mnd":"D. Minn.","cit":"Ct. Int'l Trade","ca2":"2nd Cir.","cacd":"C.D. Cal.","ord":"D. Or.","njd":"D.N.J.","cod":"D. Colo.","gamd":"M.D. Ga.","nhd":"D.N.H.","vaed":"E.D. Va.","nynd":"N.D.N.Y.","paed":"E.D. Pa.","nyed":"E.D.N.Y.","txsd":"S.D. Tex.","scd":"D.S.C.","vtd":"D. Vt.","txwd":"W.D. Tex.","kyed":"E.D. Ky.","nvd":"D. Nev.","mtd":"D. Mont.","med":"D. Me.","wvsd":"S.D. W.Va.","ca3":"3rd Cir.","azd":"D. Ariz.","wiwd":"W.D. Wis.","casd":"S.D. Cal.","pawd":"W.D. Pa.","txnd":"N.D. Tex.","ca5":"5th Cir.","ca10":"10th Cir.","lawd":"W.D. La.","hid":"D. Haw.","miwd":"W.D. Mich.","tnmd":"M.D. Tenn.","cafc":"Fed. Cir.","pamd":"M.D. Pa.","uscfc":"Ct. Fed. Claims","akd":"D. Alaska","ca7":"7th Cir.","ca6":"6th Cir.","flmd":"M.D. Fla.","ilsd":"S.D. Ill.","alsd":"S.D. Ala.","ca8":"8th Cir.","flsd":"S.D. Fla.","gand":"N.D. Ga.","ncwd":"W.D.N.C."};
function courtName(url) {
    if (!url) return "";
    const m = url.match(/\/courts\/([^/]+)\/?$/);
    return m ? (COURT_NAMES[m[1]] || m[1].toUpperCase()) : url;
}

// ── Tooltip ──
const tooltip = d3.select("body").append("div").attr("class","tooltip").style("display","none");
function showTip(evt, html) {
    tooltip.html(html).style("display","block");
    const t = tooltip.node();
    tooltip.style("left", Math.min(evt.pageX+12, window.innerWidth-t.offsetWidth-20)+"px")
           .style("top", (evt.pageY-10)+"px");
}
function hideTip() { tooltip.style("display","none"); }

// ── Shared chart: horizontal bars ──
function hBar(selector, data, opts={}) {
    const container = d3.select(selector);
    if (container.empty()) return;
    container.selectAll("*").remove();
    const width = container.node().clientWidth || 700;
    const bh = opts.barHeight || 24;
    const margin = {top:5, right:55, bottom:5, left: opts.leftMargin || 200};
    const height = data.length * bh + margin.top + margin.bottom;
    const svg = container.append("svg").attr("width",width).attr("height",height);
    const x = d3.scaleLinear().domain([0, d3.max(data, d=>d.count)]).range([margin.left, width-margin.right]);
    const y = d3.scaleBand().domain(data.map(d=>d.name)).range([margin.top, height-margin.bottom]).padding(0.22);
    svg.selectAll("rect").data(data).join("rect")
        .attr("x",margin.left).attr("y",d=>y(d.name))
        .attr("width",d=>Math.max(0,x(d.count)-margin.left)).attr("height",y.bandwidth())
        .attr("fill",d=>opts.colorFn?opts.colorFn(d):(opts.color||"#3b82f6")).attr("rx",3)
        .attr("stroke",d=>opts.strokeFn?opts.strokeFn(d):"none").attr("stroke-width",d=>opts.strokeFn&&opts.strokeFn(d)!=="none"?1.5:0);
    svg.selectAll(".bl").data(data).join("text").attr("class","bar-label")
        .attr("x",margin.left-6).attr("y",d=>y(d.name)+y.bandwidth()/2)
        .attr("text-anchor","end").attr("dominant-baseline","middle")
        .text(d=>d.name.length>32?d.name.slice(0,30)+"...":d.name);
    svg.selectAll(".bv").data(data).join("text").attr("class","bar-value")
        .attr("x",d=>x(d.count)+5).attr("y",d=>y(d.name)+y.bandwidth()/2)
        .attr("dominant-baseline","middle").text(d=>d.count);
    if (opts.onHover) {
        svg.selectAll("rect").on("mouseenter",(e,d)=>showTip(e,opts.onHover(d)))
            .on("mousemove",(e)=>showTip(e,tooltip.html())).on("mouseleave",hideTip);
    }
}

// ══════════════════════════════════════════════
// Section & Tab Navigation
// ══════════════════════════════════════════════

const renderedTabs = new Set();

document.querySelectorAll(".section-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".section-btn").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
        btn.classList.add("active");
        const sec = document.getElementById("section-" + btn.dataset.section);
        sec.classList.add("active");
        // Render first active tab of this section if needed
        const firstTab = sec.querySelector(".tab.active");
        if (firstTab && DATA && !renderedTabs.has(firstTab.dataset.tab)) {
            renderedTabs.add(firstTab.dataset.tab);
            renderTab(firstTab.dataset.tab);
        }
    });
});

document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
        const nav = tab.closest(".tab-nav") || tab.parentNode;
        const section = nav.closest(".section") || nav.parentNode;
        nav.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        section.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
        tab.classList.add("active");
        document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
        if (DATA && !renderedTabs.has(tab.dataset.tab)) {
            renderedTabs.add(tab.dataset.tab);
            renderTab(tab.dataset.tab);
        }
    });
});

// ── Load data ──
fetch("data.json").then(r => r.json()).then(data => {
    DATA = data;
    document.getElementById("lit-count").textContent = data.litigation.overview.total_dockets + " dockets";
    document.getElementById("nc-count").textContent = data.noncompliance.summary.total_cases + " cases";
    document.getElementById("nc-overlap-count").textContent = data.noncompliance.summary.overlap_judge_count;
    document.getElementById("nc-multi-count").textContent = data.noncompliance.summary.multi_violation_cases;
    // Render initial tab
    renderedTabs.add("lit-overview");
    renderTab("lit-overview");
});

// NC overlap judges lookup for cross-referencing
function ncJudgeNames() {
    if (!DATA) return new Set();
    return new Set(Object.keys(DATA.noncompliance.judges));
}

function renderTab(tabName) {
    switch(tabName) {
        case "lit-overview": renderLitOverview(); break;
        case "lit-judges": renderLitJudges(); break;
        case "lit-attorneys": renderLitAttorneys(); break;
        case "lit-actions": renderLitActions(); break;
        case "lit-explorer": initLitExplorer(); break;
        case "nc-overview": renderNcOverview(); break;
        case "nc-judges": renderNcJudges(); break;
        case "nc-violations": renderNcViolations(); break;
        case "nc-timeline": renderNcTimeline(); break;
        case "nc-explorer": initNcExplorer(); break;
    }
}

// ══════════════════════════════════════════════
// LITIGATION TRACKER
// ══════════════════════════════════════════════

function renderLitOverview() {
    const o = DATA.litigation.overview;
    const cards = [
        {n: o.total_battles, l:"Legal Battles"}, {n: o.total_dockets, l:"Dockets"},
        {n: o.total_appeals, l:"Appeals"}, {n: o.total_attorneys, l:"Attorneys"},
        {n: o.total_courts, l:"Courts"},
    ];
    document.getElementById("lit-stat-cards").innerHTML = cards.map(c =>
        `<div class="stat-card"><div class="number">${c.n}</div><div class="label">${c.l}</div></div>`
    ).join("");

    // EA bar chart
    const eaData = DATA.litigation.executive_actions.slice(0,20).map(e=>({name:e.executive_action, count:e.docket_count}));
    hBar("#lit-chart-ea", eaData, {color:"#818cf8"});

    // Court bar chart
    const courtData = DATA.litigation.court_counts.slice(0,20).map(c=>({name:courtName(c.court), count:c.count}));
    hBar("#lit-chart-courts", courtData, {color:"#2dd4bf"});

    // Timeline
    renderLitTimeline("monthly");
    document.querySelectorAll("#tab-lit-overview .toggle-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#tab-lit-overview .toggle-btn").forEach(b=>b.classList.remove("active"));
            btn.classList.add("active");
            renderLitTimeline(btn.dataset.mode);
        });
    });
}

function renderLitTimeline(mode) {
    const container = d3.select("#lit-chart-timeline");
    container.selectAll("*").remove();
    const raw = DATA.litigation.timeline;
    if (!raw.length) return;

    // Aggregate weekly data to monthly
    const monthly = {};
    raw.forEach(w => {
        const m = w.week.split("/")[0].slice(0,7);
        monthly[m] = (monthly[m]||0) + w.count;
    });
    let data = Object.entries(monthly).sort().map(([m,c])=>({month:m, count:c})).filter(d=>d.count>0 && d.month>="2024-12");

    const width = container.node().clientWidth || 700;
    const margin = {top:20, right:30, bottom:55, left:50};
    const height = 300;
    const svg = container.append("svg").attr("width",width).attr("height",height);

    const parseM = d3.timeParse("%Y-%m");
    const pts = data.map(d=>({date:parseM(d.month), count:d.count})).filter(d=>d.date);

    if (mode==="cumulative") {
        let cum = 0;
        pts.forEach(p => { cum += p.count; p.count = cum; });
    }

    const x = d3.scaleTime().domain(d3.extent(pts,d=>d.date)).range([margin.left, width-margin.right]);
    const y = d3.scaleLinear().domain([0, d3.max(pts,d=>d.count)*1.1]).range([height-margin.bottom, margin.top]);

    if (mode==="monthly") {
        const bw = Math.max(2, (width-margin.left-margin.right)/pts.length - 2);
        svg.selectAll("rect").data(pts).join("rect")
            .attr("x",d=>x(d.date)-bw/2).attr("y",d=>y(d.count))
            .attr("width",bw).attr("height",d=>height-margin.bottom-y(d.count))
            .attr("fill","#f59e0b").attr("rx",2);
    } else {
        svg.append("path").datum(pts)
            .attr("d",d3.area().x(d=>x(d.date)).y0(height-margin.bottom).y1(d=>y(d.count)).curve(d3.curveMonotoneX))
            .attr("fill","#f59e0b20");
        svg.append("path").datum(pts)
            .attr("d",d3.line().x(d=>x(d.date)).y(d=>y(d.count)).curve(d3.curveMonotoneX))
            .attr("fill","none").attr("stroke","#f59e0b").attr("stroke-width",2);
    }

    svg.append("g").attr("class","axis").attr("transform",`translate(0,${height-margin.bottom})`)
        .call(d3.axisBottom(x).ticks(d3.timeMonth.every(2)).tickFormat(d3.timeFormat("%b '%y")))
        .selectAll("text").attr("transform","rotate(-35)").attr("text-anchor","end");
    svg.append("g").attr("class","axis").attr("transform",`translate(${margin.left},0)`)
        .call(d3.axisLeft(y).ticks(5));
}

function renderLitJudges() {
    const stats = DATA.litigation.judge_stats;
    const appStats = DATA.litigation.appointer_stats;
    const ncNames = ncJudgeNames();

    // Appointer distribution
    if (appStats.distribution) {
        const entries = appStats.distribution.filter(d=>d.appointed_by!=="Unknown")
            .map(d=>({name:d.appointed_by, count:d.case_count}));
        hBar("#lit-chart-appointers", entries, {
            colorFn: d=>appointerColor(d.name),
            barHeight: 36,
        });
    }

    // Judge bar chart
    const judges = stats.slice(0,30).map(j=>({
        name: j.judge_name, count: j.case_count, appointed_by: j.appointed_by,
        inNC: ncNames.has(j.judge_name),
    }));
    hBar("#lit-chart-judges", judges, {
        colorFn: d=>appointerColor(d.appointed_by),
        strokeFn: d=>d.inNC ? "#fff" : "none",
        onHover: d => `<strong>${d.name}</strong><br>${d.count} dockets<br>Appointed by: ${d.appointed_by||"Unknown"}${d.inNC?"<br><em>Also in non-compliance dataset</em>":""}`,
    });

    // Add legend
    const legendDiv = d3.select("#lit-chart-judges").insert("div",":first-child").attr("class","chart-legend");
    Object.entries(APPOINTER_COLORS).forEach(([name,color]) => {
        if (judges.some(j=>j.appointed_by===name)) {
            legendDiv.append("div").attr("class","legend-item")
                .html(`<div class="legend-swatch" style="background:${color}"></div>${name}`);
        }
    });

    // Scatter plot
    renderLitScatter(stats);
}

function renderLitScatter(stats) {
    const container = d3.select("#lit-chart-scatter");
    container.selectAll("*").remove();
    const data = stats.filter(j=>j.case_count>=2 && (j.injunction_rate>0 || j.dismissal_rate>0));
    if (!data.length) return;

    const width = container.node().clientWidth || 700;
    const margin = {top:20, right:30, bottom:50, left:50};
    const height = 400;
    const svg = container.append("svg").attr("width",width).attr("height",height);

    const x = d3.scaleLinear().domain([0,Math.max(d3.max(data,d=>d.dismissal_rate)+5,40)]).range([margin.left,width-margin.right]);
    const y = d3.scaleLinear().domain([0,Math.max(d3.max(data,d=>d.injunction_rate)+5,40)]).range([height-margin.bottom,margin.top]);
    const r = d3.scaleSqrt().domain([0,d3.max(data,d=>d.case_count)]).range([4,20]);

    svg.selectAll("circle").data(data).join("circle")
        .attr("class","scatter-dot")
        .attr("cx",d=>x(d.dismissal_rate)).attr("cy",d=>y(d.injunction_rate))
        .attr("r",d=>r(d.case_count))
        .attr("fill",d=>appointerColor(d.appointed_by)).attr("opacity",0.5)
        .attr("stroke","#fff").attr("stroke-width",0.5)
        .on("mouseenter",(e,d)=>showTip(e,`<strong>${d.judge_name}</strong><br>${d.case_count} dockets<br>Injunction: ${d.injunction_rate}%<br>Dismissal: ${d.dismissal_rate}%<br>Appointed by: ${d.appointed_by||"Unknown"}`))
        .on("mousemove",(e)=>showTip(e,tooltip.html())).on("mouseleave",hideTip);

    svg.append("g").attr("class","axis").attr("transform",`translate(0,${height-margin.bottom})`)
        .call(d3.axisBottom(x).ticks(8));
    svg.append("g").attr("class","axis").attr("transform",`translate(${margin.left},0)`)
        .call(d3.axisLeft(y).ticks(8));
    svg.append("text").attr("x",width/2).attr("y",height-8).attr("text-anchor","middle")
        .attr("fill","var(--text-muted)").attr("font-size","11px").text("Dismissal Rate (%)");
    svg.append("text").attr("transform","rotate(-90)").attr("x",-height/2).attr("y",14)
        .attr("text-anchor","middle").attr("fill","var(--text-muted)").attr("font-size","11px").text("Injunction Rate (%)");
}

function renderLitAttorneys() {
    // Organizations
    const orgs = DATA.litigation.top_organizations.slice(0,25);
    hBar("#lit-chart-orgs", orgs.map(o=>({name:o.organization, count:o.case_count})), {
        colorFn: d => {
            const org = orgs.find(o=>o.organization===d.name);
            return org && org.role==="defendant_attorney" ? "#ef4444" : "#3b82f6";
        }
    });

    // Plaintiff attorneys
    hBar("#lit-chart-plaintiff-attys",
        DATA.litigation.top_attorneys.plaintiff.slice(0,15).map(a=>({name:a.name, count:a.case_count})),
        {leftMargin:180}
    );

    // Defendant attorneys
    hBar("#lit-chart-defendant-attys",
        DATA.litigation.top_attorneys.defendant.slice(0,15).map(a=>({name:a.name, count:a.case_count})),
        {colorFn:()=>"#ef4444", leftMargin:180}
    );
}

function renderLitActions() {
    const container = d3.select("#lit-chart-ea-status");
    container.selectAll("*").remove();
    const eaData = DATA.litigation.ea_status_breakdown.slice(0,15);
    if (!eaData.length) return;

    // Collect all status categories
    const allCats = new Set();
    eaData.forEach(ea => Object.keys(ea.statuses).forEach(s => allCats.add(s)));
    const categories = [...allCats].sort();

    const width = container.node().clientWidth || 700;
    const margin = {top:10, right:20, bottom:120, left:50};
    const height = 450;
    const svg = container.append("svg").attr("width",width).attr("height",height);

    const x = d3.scaleBand().domain(eaData.map(d=>d.executive_action)).range([margin.left,width-margin.right]).padding(0.2);
    const y = d3.scaleLinear().domain([0,d3.max(eaData,d=>d.total)*1.1]).range([height-margin.bottom, margin.top]);

    const stack = d3.stack().keys(categories).value((d,key)=>d.statuses[key]||0);
    const series = stack(eaData);

    svg.selectAll("g.series").data(series).join("g").attr("class","series")
        .attr("fill",d=>STATUS_COLORS[d.key]||"#999")
        .selectAll("rect").data(d=>d).join("rect")
        .attr("x",d=>x(d.data.executive_action))
        .attr("y",d=>y(d[1])).attr("height",d=>y(d[0])-y(d[1]))
        .attr("width",x.bandwidth()).attr("rx",2)
        .on("mouseenter",(e,d)=>{
            const cat = d3.select(e.target.parentNode).datum().key;
            showTip(e,`<strong>${d.data.executive_action}</strong><br>${cat}: ${d[1]-d[0]}<br>Total: ${d.data.total}`);
        })
        .on("mousemove",(e)=>showTip(e,tooltip.html())).on("mouseleave",hideTip);

    svg.append("g").attr("class","axis").attr("transform",`translate(0,${height-margin.bottom})`)
        .call(d3.axisBottom(x)).selectAll("text")
        .attr("transform","rotate(-45)").attr("text-anchor","end").attr("font-size","9px")
        .text(d=>d.length>25?d.slice(0,23)+"...":d);
    svg.append("g").attr("class","axis").attr("transform",`translate(${margin.left},0)`)
        .call(d3.axisLeft(y).ticks(5));

    // Legend
    const legend = container.insert("div",":first-child").attr("class","chart-legend");
    categories.forEach(cat => {
        legend.append("div").attr("class","legend-item")
            .html(`<div class="legend-swatch" style="background:${STATUS_COLORS[cat]||'#999'}"></div>${cat}`);
    });
}

function initLitExplorer() {
    const cases = DATA.litigation.cases;
    const statuses = [...new Set(cases.map(c=>c.status_category))].sort();
    const courts = [...new Set(cases.map(c=>c.court_display).filter(Boolean))].sort();

    const sSel = document.getElementById("lit-filter-status");
    statuses.forEach(s => { const o=document.createElement("option"); o.value=s; o.textContent=s; sSel.appendChild(o); });
    const cSel = document.getElementById("lit-filter-court");
    courts.forEach(c => { const o=document.createElement("option"); o.value=c; o.textContent=c; cSel.appendChild(o); });

    document.getElementById("lit-explorer-total").textContent = cases.length;

    let viewMode = "all";
    document.getElementById("lit-view-all").addEventListener("click", ()=>{viewMode="all"; document.getElementById("lit-view-all").classList.add("active"); document.getElementById("lit-view-battles").classList.remove("active"); renderLitCases();});
    document.getElementById("lit-view-battles").addEventListener("click", ()=>{viewMode="battles"; document.getElementById("lit-view-battles").classList.add("active"); document.getElementById("lit-view-all").classList.remove("active"); renderLitCases();});

    const render = () => renderLitCases();
    document.getElementById("lit-search").addEventListener("input", render);
    sSel.addEventListener("change", render);
    cSel.addEventListener("change", render);

    function renderLitCases() {
        const search = document.getElementById("lit-search").value.toLowerCase();
        const status = document.getElementById("lit-filter-status").value;
        const court = document.getElementById("lit-filter-court").value;

        let filtered = cases;
        if (viewMode==="battles") {
            // Show first case per battle_id
            const seen = new Set();
            filtered = filtered.filter(c => {
                const bid = c.battle_id;
                if (!bid || seen.has(bid)) return false;
                seen.add(bid);
                return true;
            });
        }

        filtered = filtered.filter(c => {
            if (search && !(
                (c.case_name||"").toLowerCase().includes(search) ||
                (c.judge_name||"").toLowerCase().includes(search) ||
                (c.executive_action_display||"").toLowerCase().includes(search) ||
                (c.docket_number||"").toLowerCase().includes(search)
            )) return false;
            if (status && c.status_category !== status) return false;
            if (court && c.court_display !== court) return false;
            return true;
        });

        document.getElementById("lit-explorer-showing").textContent = filtered.length;
        const shown = filtered.slice(0,50);
        const ncNames = ncJudgeNames();

        document.getElementById("lit-case-list").innerHTML = shown.map(c => {
            const clUrl = c.courtlistener_url || (c.courtlistener_docket_id ? `https://www.courtlistener.com/docket/${c.courtlistener_docket_id}/` : "");
            const inNC = ncNames.has(c.judge_name);
            return `<div class="case-item">
                <div class="case-item-header">
                    <div>
                        <span class="status-tag" style="background:${STATUS_COLORS[c.status_category]||'#999'}33;color:${STATUS_COLORS[c.status_category]||'#999'}">${c.status_category}</span>
                        ${c.is_appeal ? '<span class="status-tag" style="background:#6366f133;color:#6366f1">Appeal</span>' : ''}
                    </div>
                    <span class="case-date">${c.date_filed||""}</span>
                </div>
                <div class="case-name">${c.case_name}</div>
                <div class="case-meta">
                    ${c.docket_number||""} &middot; ${c.court_display} &middot; ${c.judge_name||""}
                    ${c.appointed_by?`<span class="appointer-tag" style="background:${appointerColor(c.appointed_by)}22;color:${appointerColor(c.appointed_by)}">${c.appointed_by}</span>`:""}
                    ${inNC?'<span class="appointer-tag" style="background:#ef444422;color:#ef4444">Non-compliance</span>':""}
                </div>
                <div class="case-meta">${c.executive_action_display||""}</div>
                ${c.summary?`<div class="case-description" onclick="this.classList.toggle('expanded')">${c.summary}</div>`:""}
                <div class="case-links">
                    ${clUrl?`<a href="${clUrl}" target="_blank">CourtListener</a>`:""}
                </div>
            </div>`;
        }).join("") + (filtered.length>50?`<div style="color:var(--text-dim);text-align:center;padding:0.75rem">Showing 50 of ${filtered.length}. Use filters to narrow.</div>`:"");
    }

    renderLitCases();
}

// ══════════════════════════════════════════════
// NON-COMPLIANCE
// ══════════════════════════════════════════════

function renderNcOverview() {
    const s = DATA.noncompliance.summary;
    const cards = [
        {n:s.total_cases, l:"Cases"}, {n:s.total_judges, l:"Judges"},
        {n:s.overlap_judge_count, l:"Judges in Both Datasets"},
        {n:s.total_jurisdictions, l:"Jurisdictions"},
        {n:s.egregious_count, l:"Flagged Egregious"},
        {n:s.multi_violation_cases, l:"Multi-Violation Cases"},
    ];
    document.getElementById("nc-stat-cards").innerHTML = cards.map(c =>
        `<div class="stat-card"><div class="number">${c.n}</div><div class="label">${c.l}</div></div>`
    ).join("");

    // Violations by type (severity order)
    const order = s.violation_severity_order;
    const vtData = order.filter(v=>s.violation_type_counts[v]).map(v=>({name:v, count:s.violation_type_counts[v]}));
    hBar("#nc-chart-violations", vtData, {colorFn:d=>violationColor(d.name), barHeight:28});

    // Jurisdictions
    const jData = Object.entries(s.jurisdiction_counts).map(([n,c])=>({
        name: n.replace("District of ","D. ").replace("Eastern District of ","E.D. ").replace("Western District of ","W.D. ")
              .replace("Southern District of ","S.D. ").replace("Northern District of ","N.D. ")
              .replace("Central District of ","C.D. ").replace("Middle District of ","M.D. ")
              .replace("District Court for the ",""), count:c
    })).sort((a,b)=>b.count-a.count);
    hBar("#nc-chart-jurisdictions", jData);

    // Appointers
    const aData = Object.entries(s.appointer_distribution).map(([n,c])=>({name:n, count:c})).sort((a,b)=>b.count-a.count);
    hBar("#nc-chart-appointers", aData, {colorFn:d=>appointerColor(d.name), barHeight:36});
}

function renderNcJudges() {
    const judges = DATA.noncompliance.overlap_judges;
    const container = d3.select("#nc-chart-overlap");
    container.selectAll("*").remove();

    const legend = container.append("div").attr("class","chart-legend");
    legend.append("div").attr("class","legend-item").html('<div class="legend-swatch" style="background:#ef4444"></div>Non-compliance');
    legend.append("div").attr("class","legend-item").html('<div class="legend-swatch" style="background:#3b82f6"></div>Structural litigation');

    const width = container.node().clientWidth || 700;
    const bh = 32;
    const margin = {top:10, right:70, bottom:10, left:200};
    const height = judges.length * bh + margin.top + margin.bottom;
    const svg = container.append("svg").attr("width",width).attr("height",height);

    const maxVal = d3.max(judges, d=>d.total);
    const x = d3.scaleLinear().domain([0,maxVal]).range([margin.left, width-margin.right]);
    const y = d3.scaleBand().domain(judges.map(d=>d.name)).range([margin.top, height-margin.bottom]).padding(0.22);

    const g = svg.selectAll(".judge-bar").data(judges).join("g").attr("class","judge-bar")
        .on("click",(e,d)=>showNcJudgeDetail(d))
        .on("mouseenter",(e,d)=>showTip(e,`<strong>${d.name}</strong><br>Appointed by: ${d.appointed_by||"Unknown"}<br>Non-compliance: ${d.nc_cases}<br>Litigation: ${d.lit_cases}<br><em>Click for details</em>`))
        .on("mousemove",(e)=>showTip(e,tooltip.html())).on("mouseleave",hideTip);

    g.append("rect").attr("x",margin.left).attr("y",d=>y(d.name))
        .attr("width",d=>x(d.nc_cases)-margin.left).attr("height",y.bandwidth())
        .attr("fill","#ef4444").attr("rx",3);
    g.append("rect").attr("x",d=>x(d.nc_cases)).attr("y",d=>y(d.name))
        .attr("width",d=>x(d.nc_cases+d.lit_cases)-x(d.nc_cases)).attr("height",y.bandwidth())
        .attr("fill","#3b82f6").attr("rx",3);
    g.append("rect").attr("x",margin.left-5).attr("y",d=>y(d.name))
        .attr("width",3).attr("height",y.bandwidth())
        .attr("fill",d=>appointerColor(d.appointed_by)).attr("rx",1);
    g.append("text").attr("class","bar-label").attr("x",margin.left-10).attr("y",d=>y(d.name)+y.bandwidth()/2)
        .attr("text-anchor","end").attr("dominant-baseline","middle").text(d=>d.name);
    g.append("text").attr("class","bar-value").attr("x",d=>x(d.total)+5).attr("y",d=>y(d.name)+y.bandwidth()/2)
        .attr("dominant-baseline","middle").text(d=>`${d.nc_cases} + ${d.lit_cases}`);

    // All judges chart
    const allJudges = Object.values(DATA.noncompliance.judges).sort((a,b)=>b.nc_case_count-a.nc_case_count).slice(0,40);
    hBar("#nc-chart-all-judges", allJudges.map(j=>({name:j.name, count:j.nc_case_count, appointed_by:j.appointed_by, inLit:j.in_litigation_tracker})), {
        colorFn: d=>appointerColor(d.appointed_by),
        strokeFn: d=>d.inLit?"#fff":"none",
    });
    const allLegend = d3.select("#nc-chart-all-judges").insert("div",":first-child").attr("class","chart-legend");
    Object.entries(APPOINTER_COLORS).forEach(([n,c])=>{
        if(allJudges.some(j=>j.appointed_by===n))
            allLegend.append("div").attr("class","legend-item").html(`<div class="legend-swatch" style="background:${c}"></div>${n}`);
    });
}

function showNcJudgeDetail(judge) {
    const panel = document.getElementById("nc-judge-detail");
    panel.style.display = "block";
    document.getElementById("nc-judge-detail-name").textContent = judge.name;

    const ncCases = DATA.noncompliance.cases.filter(c=>c.judge===judge.name);
    document.getElementById("nc-judge-detail-content").innerHTML = `
        <div style="margin-bottom:0.75rem;color:var(--text-muted);font-size:0.8rem">
            Appointed by: <span class="appointer-tag" style="background:${appointerColor(judge.appointed_by)}22;color:${appointerColor(judge.appointed_by)}">${judge.appointed_by||"Unknown"}</span>
            &middot; ${judge.nc_cases} non-compliance &middot; ${judge.lit_cases} structural litigation
        </div>
        <div class="detail-grid">
            <div class="detail-section">
                <h3>Non-Compliance Cases (${ncCases.length})</h3>
                ${ncCases.map(c=>`<div class="detail-case">
                    <div class="case-name">${c.case_name}</div>
                    <div class="case-meta">${c.case_no} &middot; ${c.jurisdiction}</div>
                    <div>${c.violation_types.map(v=>`<span class="violation-tag" style="background:${violationColor(v)}22;color:${violationColor(v)}">${v}</span>`).join("")}</div>
                </div>`).join("")}
            </div>
            <div class="detail-section">
                <h3>Structural Litigation (${judge.lit_case_details.length})</h3>
                ${judge.lit_case_details.map(c=>`<div class="detail-case">
                    <div class="case-name">${c.case_name}</div>
                    <div class="case-meta">${c.docket_number||""} &middot; ${c.status||""}</div>
                    <div class="case-meta">${c.executive_action||""}</div>
                </div>`).join("")}
            </div>
        </div>`;
    panel.scrollIntoView({behavior:"smooth", block:"nearest"});
}

function renderNcViolations() {
    // Co-occurrence matrix
    const coData = DATA.noncompliance.cooccurrence;
    if (!coData.length) return;
    const types = new Set();
    coData.forEach(d=>{types.add(d.source);types.add(d.target);});
    const typeList = [...types];

    const container = d3.select("#nc-chart-cooccurrence");
    const size = Math.min(container.node().clientWidth||700, 700);
    const margin = {top:150, right:20, bottom:20, left:200};
    const cellSize = Math.floor((size-margin.left-margin.right)/typeList.length);
    const w = margin.left+cellSize*typeList.length+margin.right;
    const h = margin.top+cellSize*typeList.length+margin.bottom;
    const svg = container.append("svg").attr("width",w).attr("height",h);

    const maxC = d3.max(coData,d=>d.count);
    const color = d3.scaleSequential(d3.interpolateYlOrRd).domain([0,maxC]);
    const lookup = {};
    coData.forEach(d=>{lookup[d.source+"|"+d.target]=d.count; lookup[d.target+"|"+d.source]=d.count;});

    svg.selectAll(".rl").data(typeList).join("text").attr("class","matrix-label")
        .attr("x",margin.left-6).attr("y",(d,i)=>margin.top+i*cellSize+cellSize/2)
        .attr("text-anchor","end").attr("dominant-baseline","middle")
        .text(d=>d.length>28?d.slice(0,26)+"...":d);
    svg.selectAll(".cl").data(typeList).join("text").attr("class","matrix-label")
        .attr("transform",(d,i)=>`translate(${margin.left+i*cellSize+cellSize/2},${margin.top-6}) rotate(-45)`)
        .attr("text-anchor","start").text(d=>d.length>22?d.slice(0,20)+"...":d);

    for (let i=0;i<typeList.length;i++) for(let j=0;j<typeList.length;j++){
        if(i===j)continue;
        const c=lookup[typeList[i]+"|"+typeList[j]]||0;
        if(!c)continue;
        svg.append("rect").attr("class","matrix-cell")
            .attr("x",margin.left+j*cellSize).attr("y",margin.top+i*cellSize)
            .attr("width",cellSize-1).attr("height",cellSize-1).attr("fill",color(c)).attr("rx",2)
            .on("mouseenter",(e)=>showTip(e,`<strong>${typeList[i]}</strong> + <strong>${typeList[j]}</strong><br>${c} cases`))
            .on("mousemove",(e)=>showTip(e,tooltip.html())).on("mouseleave",hideTip);
        if(cellSize>28) svg.append("text").attr("x",margin.left+j*cellSize+cellSize/2).attr("y",margin.top+i*cellSize+cellSize/2)
            .attr("text-anchor","middle").attr("dominant-baseline","middle")
            .attr("fill",c>maxC*0.6?"#000":"#fff").attr("font-size","10px").attr("font-weight","600").text(c);
    }

    // Violations by jurisdiction heatmap
    renderNcViolByJuris();
}

function renderNcViolByJuris() {
    const s = DATA.noncompliance.summary;
    const topJ = Object.entries(s.jurisdiction_counts).sort((a,b)=>b[1]-a[1]).slice(0,8).map(d=>d[0]);
    const vTypes = s.violation_severity_order.filter(v=>s.violation_type_counts[v]);

    const matrix = {};
    topJ.forEach(j=>{matrix[j]={};vTypes.forEach(v=>matrix[j][v]=0);});
    DATA.noncompliance.cases.forEach(c=>{
        if(!topJ.includes(c.jurisdiction))return;
        c.violation_types.forEach(v=>{if(matrix[c.jurisdiction][v]!==undefined)matrix[c.jurisdiction][v]++;});
    });

    const container = d3.select("#nc-chart-viol-by-juris");
    const margin={top:150,right:20,bottom:20,left:200};
    const cw=50, ch=28;
    const w=margin.left+vTypes.length*cw+margin.right;
    const h=margin.top+topJ.length*ch+margin.bottom;
    const svg=container.append("svg").attr("width",Math.min(w,container.node().clientWidth||700)).attr("height",h).attr("viewBox",`0 0 ${w} ${h}`);

    const maxVal=d3.max(topJ,j=>d3.max(vTypes,v=>matrix[j][v]));
    const color=d3.scaleSequential(d3.interpolateBlues).domain([0,maxVal]);

    svg.selectAll(".rl").data(topJ).join("text").attr("class","matrix-label")
        .attr("x",margin.left-6).attr("y",(d,i)=>margin.top+i*ch+ch/2)
        .attr("text-anchor","end").attr("dominant-baseline","middle")
        .text(d=>d.replace("District of ","D. ").replace(/Eastern |Western |Southern |Northern |Central |Middle /,""));
    svg.selectAll(".cl").data(vTypes).join("text").attr("class","matrix-label")
        .attr("transform",(d,i)=>`translate(${margin.left+i*cw+cw/2},${margin.top-6}) rotate(-50)`)
        .attr("text-anchor","start").attr("font-size","9px")
        .text(d=>d.length>20?d.slice(0,18)+"...":d);

    topJ.forEach((j,ri)=>vTypes.forEach((v,ci)=>{
        const val=matrix[j][v];
        svg.append("rect").attr("x",margin.left+ci*cw).attr("y",margin.top+ri*ch)
            .attr("width",cw-2).attr("height",ch-2).attr("fill",val>0?color(val):"#1a1d27").attr("rx",2)
            .on("mouseenter",(e)=>showTip(e,`<strong>${j}</strong><br>${v}: ${val}`))
            .on("mousemove",(e)=>showTip(e,tooltip.html())).on("mouseleave",hideTip);
        if(val>0) svg.append("text").attr("x",margin.left+ci*cw+(cw-2)/2).attr("y",margin.top+ri*ch+(ch-2)/2)
            .attr("text-anchor","middle").attr("dominant-baseline","middle")
            .attr("fill",val>maxVal*0.5?"#000":"#9ca3af").attr("font-size","9px").text(val);
    }));
}

function renderNcTimeline() {
    const tData = DATA.noncompliance.timeline;
    if(!tData.length) return;
    const container = d3.select("#nc-chart-timeline");
    container.selectAll("*").remove();
    const width = container.node().clientWidth||700;
    const margin={top:20,right:30,bottom:55,left:50};
    const height=340;
    const svg=container.append("svg").attr("width",width).attr("height",height);

    const parseM=d3.timeParse("%Y-%m");
    const pts=tData.map(d=>({date:parseM(d.month),total:d.total,byType:d.by_type})).filter(d=>d.date);

    const x=d3.scaleTime().domain(d3.extent(pts,d=>d.date)).range([margin.left,width-margin.right]);
    const y=d3.scaleLinear().domain([0,d3.max(pts,d=>d.total)*1.1]).range([height-margin.bottom,margin.top]);

    svg.append("path").datum(pts).attr("d",d3.area().x(d=>x(d.date)).y0(height-margin.bottom).y1(d=>y(d.total)).curve(d3.curveMonotoneX)).attr("fill","#3b82f620");
    svg.append("path").datum(pts).attr("d",d3.line().x(d=>x(d.date)).y(d=>y(d.total)).curve(d3.curveMonotoneX)).attr("fill","none").attr("stroke","#3b82f6").attr("stroke-width",2);
    svg.selectAll("circle").data(pts).join("circle").attr("cx",d=>x(d.date)).attr("cy",d=>y(d.total))
        .attr("r",4).attr("fill","#3b82f6").attr("stroke","#0f1117").attr("stroke-width",2)
        .on("mouseenter",(e,d)=>{
            const bd=Object.entries(d.byType).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${k}: ${v}`).join("<br>");
            showTip(e,`<strong>${d3.timeFormat("%B %Y")(d.date)}</strong><br>${d.total} cases<br><br>${bd}`);
        }).on("mousemove",(e)=>showTip(e,tooltip.html())).on("mouseleave",hideTip);

    svg.append("g").attr("class","axis").attr("transform",`translate(0,${height-margin.bottom})`)
        .call(d3.axisBottom(x).ticks(d3.timeMonth.every(2)).tickFormat(d3.timeFormat("%b '%y")))
        .selectAll("text").attr("transform","rotate(-35)").attr("text-anchor","end");
    svg.append("g").attr("class","axis").attr("transform",`translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5));
}

function initNcExplorer() {
    const cases = DATA.noncompliance.cases;
    const s = DATA.noncompliance.summary;

    const jSel=document.getElementById("nc-filter-jurisdiction");
    Object.keys(s.jurisdiction_counts).sort().forEach(j=>{const o=document.createElement("option");o.value=j;o.textContent=j;jSel.appendChild(o);});
    const vSel=document.getElementById("nc-filter-violation");
    s.violation_severity_order.filter(v=>s.violation_type_counts[v]).forEach(v=>{const o=document.createElement("option");o.value=v;o.textContent=v;vSel.appendChild(o);});
    const aSel=document.getElementById("nc-filter-appointer");
    Object.keys(s.appointer_distribution).sort().forEach(a=>{const o=document.createElement("option");o.value=a;o.textContent=a;aSel.appendChild(o);});

    document.getElementById("nc-explorer-total").textContent=cases.length;

    const render=()=>renderNcCases();
    document.getElementById("nc-search").addEventListener("input",render);
    jSel.addEventListener("change",render);
    vSel.addEventListener("change",render);
    aSel.addEventListener("change",render);

    function renderNcCases(){
        const search=document.getElementById("nc-search").value.toLowerCase();
        const jurisdiction=jSel.value;
        const violation=vSel.value;
        const appointer=aSel.value;

        let filtered=cases.filter(c=>{
            if(search&&!((c.case_name||"").toLowerCase().includes(search)||(c.judge||"").toLowerCase().includes(search)||(c.jurisdiction||"").toLowerCase().includes(search)||(c.case_no||"").toLowerCase().includes(search)))return false;
            if(jurisdiction&&c.jurisdiction!==jurisdiction)return false;
            if(violation&&!c.violation_types.includes(violation))return false;
            if(appointer&&c.appointed_by!==appointer)return false;
            return true;
        });

        document.getElementById("nc-explorer-showing").textContent=filtered.length;
        const shown=filtered.slice(0,50);

        document.getElementById("nc-case-list").innerHTML=shown.map(c=>`
            <div class="case-item">
                <div class="case-item-header">
                    <div>
                        <span class="jurisdiction-tag">${c.jurisdiction}</span>
                        ${c.violation_types.map(v=>`<span class="violation-tag" style="background:${violationColor(v)}22;color:${violationColor(v)}">${v}</span>`).join("")}
                    </div>
                    <span class="case-date">${c.dates[0]||""}</span>
                </div>
                <div class="case-name" style="font-weight:600;margin:0.2rem 0">${c.case_name}</div>
                <div class="case-meta">
                    ${c.case_no} &middot; ${c.judge}
                    ${c.appointed_by?`<span class="appointer-tag" style="background:${appointerColor(c.appointed_by)}22;color:${appointerColor(c.appointed_by)}">${c.appointed_by}</span>`:""}
                </div>
                <div class="case-description" onclick="this.classList.toggle('expanded')">${c.description}</div>
                <div class="case-links">
                    ${c.link_docket?`<a href="${c.link_docket}" target="_blank">Full Docket</a>`:""}
                </div>
            </div>
        `).join("")+(filtered.length>50?`<div style="color:var(--text-dim);text-align:center;padding:0.75rem">Showing 50 of ${filtered.length}. Use filters to narrow.</div>`:"");
    }

    renderNcCases();
}
