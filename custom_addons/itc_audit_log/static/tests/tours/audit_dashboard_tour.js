/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("itc_audit_log_dashboard", {
    test: true,
    url: "/web#action=itc_audit_log.dashboard",
    steps: () => [
        {
            content: "the four KPI cards are there",
            trigger: ".o_audit_dashboard .o_audit_kpi_rules",
        },
        {
            content: "Chart.js drew the charts (it styles the canvas once it has drawn)",
            trigger: ".o_audit_dashboard .o_audit_chart canvas[style*='box-sizing']",
        },
        {
            content: "change the period",
            trigger: ".o_audit_dashboard .o_audit_period",
            run: "select all",
        },
        {
            content: "the figures are loaded again",
            trigger: ".o_audit_dashboard .o_audit_kpi_entries",
        },
        {
            content: "compare with the snapshot",
            trigger: ".o_audit_dashboard .o_audit_compare_button",
            run: "click",
        },
        {
            content: "the differences are shown on the dashboard",
            trigger: ".o_audit_dashboard .o_audit_diff",
        },
        {
            content: "go to the journal",
            trigger: ".o_audit_dashboard .o_audit_open_journal",
            run: "click",
        },
        {
            content: "the journal list is open",
            trigger: ".o_list_view, .o_view_nocontent",
        },
    ],
});
