/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";

// the server sends 2026-11-16 (or 2026-11 for a month), we show 16 nov. (or nov. 2026), in UTC so the day never shifts
function formatLabel(label, unit) {
    const isDay = unit === "day";
    const date = new Date(isDay ? label : label + "-01");
    const format = isDay ? { day: "numeric", month: "short" } : { month: "short", year: "numeric" };
    return date.toLocaleDateString("fr-FR", { ...format, timeZone: "UTC" });
}

export class AuditDashboard extends Component {
    static template = "itc_audit_log.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dayCanvas = useRef("dayCanvas");
        this.entityCanvas = useRef("entityCanvas");
        // the two Chart.js objects, kept to destroy them before drawing new ones
        this.charts = [];
        this.drawnFor = null;
        this.state = useState({
            period: "30",
            data: null,
            snapshotId: 0,
            diff: null,
        });

        onWillStart(async () => {
            // Chart.js ships with odoo, nothing is downloaded from the internet
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.load();
        });
        onMounted(() => this.drawCharts());
        onPatched(() => this.drawCharts());
        onWillUnmount(() => this.destroyCharts());
    }

    async load() {
        const data = await this.orm.call("audit.dashboard", "get_data", [this.state.period]);
        this.state.data = data;
        if (!data.snapshots.some((snapshot) => snapshot.id === this.state.snapshotId)) {
            this.state.snapshotId = data.snapshots.length ? data.snapshots[0].id : 0;
            this.state.diff = null;
        }
    }

    async onPeriodChange(ev) {
        this.state.period = ev.target.value;
        await this.load();
    }

    destroyCharts() {
        for (const chart of this.charts) {
            chart.destroy();
        }
        this.charts = [];
    }

    drawCharts() {
        const data = this.state.data;
        // only draw again when the figures changed, not on every click of the page
        if (!data || this.drawnFor === data || !this.dayCanvas.el || !this.entityCanvas.el) {
            return;
        }
        this.drawnFor = data;
        this.destroyCharts();
        this.charts.push(
            new Chart(this.dayCanvas.el, {
                type: "bar",
                data: {
                    labels: data.per_day.labels.map((label) => formatLabel(label, data.per_day.unit)),
                    datasets: [
                        {
                            label: "Opérations",
                            data: data.per_day.values,
                            backgroundColor: "#0f766e",
                            maxBarThickness: 40,
                        },
                    ],
                },
                options: {
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                    },
                },
            }),
            new Chart(this.entityCanvas.el, {
                type: "bar",
                data: {
                    labels: data.per_entity.labels,
                    datasets: [
                        {
                            label: "Opérations",
                            data: data.per_entity.values,
                            backgroundColor: "#f59e0b",
                            maxBarThickness: 28,
                        },
                    ],
                },
                options: {
                    indexAxis: "y",
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true, ticks: { precision: 0 } },
                        y: { grid: { display: false } },
                    },
                },
            })
        );
    }

    // one bar needs about 36px, so the chart grows with the number of models instead of squeezing them
    get entityChartHeight() {
        const count = this.state.data ? this.state.data.per_entity.labels.length : 0;
        return Math.max(260, count * 36 + 60);
    }

    openJournal() {
        this.action.doAction("itc_audit_log.action_audit_log");
    }

    openConfiguration() {
        this.action.doAction("itc_audit_log.action_audit_model_config");
    }

    openSnapshots() {
        this.action.doAction("itc_audit_log.action_audit_snapshot");
    }

    openPurge() {
        // the figures are drawn again when the purge window closes
        this.action.doAction("itc_audit_log.action_audit_purge_wizard", {
            onClose: () => this.load(),
        });
    }

    async compare() {
        if (this.state.snapshotId) {
            this.state.diff = await this.orm.call("audit.dashboard", "compare", [this.state.snapshotId]);
        }
    }

    async openComparisonList() {
        const action = await this.orm.call("audit.snapshot", "action_compare", [[this.state.snapshotId]]);
        this.action.doAction(action);
    }
}

registry.category("actions").add("itc_audit_log.dashboard", AuditDashboard);
