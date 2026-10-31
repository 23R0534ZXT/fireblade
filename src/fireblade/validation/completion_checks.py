"""Acceptance checks for derived columns, TLE migration and complete expansion."""

import csv
import hashlib
from pathlib import Path
import shutil
from PySide6.QtWidgets import QFileDialog
from fireblade.core.engine import Case
from fireblade.core.models import View, Summary
from fireblade.core.profiles import detect_profile, profile_transformations
from fireblade.core.filter_text import parse_filter
from fireblade.runtime.resources import resource_path


def check_completion(window, directory, settle, check, expect, captures=None):
    directory = Path(directory)
    fixtures = resource_path("qa")
    if not fixtures.exists():
        fixtures = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
    source = directory / "upstream-plaso.csv"
    shutil.copy2(fixtures / "tle-exports" / "SuperTimelinePlaso.csv", source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    case = Case(directory / "completion.timeline", settings=window.settings)
    case.import_csv(source)
    window.detach()
    window.attach(case)
    settle()

    def normalize():
        from fireblade.ui.derived_columns import add_columns

        add_columns(
            window, profile_transformations(detect_profile(case.headers), case.headers)
        )
        settle()
        values = case.page(View())
        expect(
            values[0][-3:] == ("2020-01-02T03:04:05.000000000Z", "1", "FileOpening"),
            "Upstream Plaso transformation differs",
        )
        expect(
            values[1][-2:] == ("10", "WebHistory"), "MACB flags or web category differ"
        )
        expect(values[2][-1] == "LogFile", "Event log category differs")
        expect(
            window.model.columnCount() == len(case.headers) + 1,
            "Grid schema did not update",
        )

    check("official_plaso_fixture_date_macb_category_and_gui_schema", normalize)

    def expressions():
        view = View(
            expression=parse_filter(
                "GetYear([Timestamp]) = 2020 And Iif(ToInt([Fireblade_MACBMask]) = 1, True, False)",
                case.headers,
            )
        )
        window.set_view(view)
        settle()
        expect(
            window.model.rowCount() == 1,
            "Nested text/date/calculation expression differs",
        )
        expect(
            case.count(
                View(
                    expression=parse_filter(
                        "[Line]=2 And Contains([desc],'example')", case.headers
                    )
                )
            )
            == 1,
            "Virtual source line differs",
        )

    check("advanced_nested_expressions_and_virtual_source_fields", expressions)

    def layout():
        original = QFileDialog.getOpenFileName
        QFileDialog.getOpenFileName = lambda *a, **k: (
            str(fixtures / "tle-layouts" / "SuperTimeline.layout"),
            "",
        )
        try:
            window.import_layout()
            settle()
        finally:
            QFileDialog.getOpenFileName = original
        expect(
            len(window.view.format_rules) == 7, "Official TLE color rules not migrated"
        )
        expect(
            case.count(window.view) == 3, "Layout migration changed source record count"
        )

    check("official_tle_layout_import_and_color_expressions", layout)

    def outline():
        view = View(groups=[4, 5], summaries=[Summary(13, "sum")])
        window.set_view(view)
        settle()
        window.expand_groups()
        settle()
        expect(window.view.expand_all, "Complete expansion not enabled")
        expect(
            len([n for n in window.model.root.children if not n.group]) == 3,
            "Complete expansion lost leaves",
        )
        window.collapse_groups()
        settle()
        expect(
            not window.view.expand_all and window.model.rowCount() == 3,
            "Collapse did not restore hierarchical mode",
        )

    check("complete_disk_indexed_group_expansion_and_collapse", outline)

    def precision():
        from fireblade.core.derived import timestamp_sql, literal

        checks = [
            ("filetime", "116444736001234567", "1970-01-01T00:00:00.123456700Z"),
            ("unix_ns", "-1", "1969-12-31T23:59:59.999999999Z"),
            ("dotnet", "0", "0001-01-01T00:00:00.000000000Z"),
        ]
        for fmt, value, expected in checks:
            expect(
                case.db.execute(
                    "SELECT " + timestamp_sql(literal(value), fmt)
                ).fetchone()[0]
                == expected,
                "Timestamp precision/conversion differs in bundled runtime",
            )

        expect(
            case.db.execute(
                "SELECT "
                + timestamp_sql(
                    literal("2026-01-01 12:00:00.1234567"),
                    "iso",
                    literal("Europe/Paris"),
                )
            ).fetchone()[0]
            == "2026-01-01T11:00:00.123456700Z",
            "Named timezone data unavailable in bundled runtime",
        )
        expect(
            case.count(
                View(
                    expression=parse_filter(
                        "AddTicks(#2026-01-01T00:00:00.1234567Z#,1) = #2026-01-01T00:00:00.1234568Z#",
                        case.headers,
                    )
                )
            )
            == 3,
            "Bundled date expressions lost a FILETIME tick",
        )

    check("bundled_native_timestamp_precision_and_epoch_boundaries", precision)

    def provenance():
        expect(
            hashlib.sha256(source.read_bytes()).hexdigest() == before,
            "Transformation changed the source",
        )
        target = directory / "derived.csv"
        case.export(target, View(), columns=[17, 18, 19])
        with target.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        expect(
            len(rows) == 4 and rows[1][0].endswith(".000000000Z"),
            "Derived export differs",
        )
        expect(
            case.info["headers"][0] == "date" and len(case.info["headers"]) == 17,
            "Source schema was rewritten",
        )
        if captures:
            window.grab().save(str(Path(captures) / "completion-full-groups.png"))

    check("derived_export_and_immutable_source_provenance", provenance)

    def settings():
        import copy
        from PySide6.QtWidgets import QApplication
        from fireblade.core.preferences import save_preferences

        old = copy.deepcopy(window.preferences)
        font = QApplication.font()
        path = directory / "TLE_settings.xml"
        path.write_text(
            "<Settings><CopyColumnHeaders>false</CopyColumnHeaders><CopyRightClick>true</CopyRightClick><DateTimeFormat>yyyy-MM-dd HH:mm:ss.fffffffK</DateTimeFormat><DetailsOnTop>true</DetailsOnTop><FontName>Consolas</FontName><FontSize>12.5</FontSize><MultilineTabs>true</MultilineTabs><Theme>Office 2019 Black</Theme></Settings>"
        )
        before = path.read_bytes()
        original = QFileDialog.getOpenFileName
        QFileDialog.getOpenFileName = lambda *a, **k: (str(path), "")
        try:
            window.import_tle_settings()
            settle()
            expect(
                window.preferences.font_size == 12.5
                and window.preferences.theme == "dark",
                "TLE font/theme settings differ",
            )
            expect(
                window.splitter.widget(0) is window.details,
                "DetailsOnTop was not migrated",
            )
            expect(
                window.model.date_format == "custom",
                "Custom date format was not applied",
            )
            expect(path.read_bytes() == before, "Settings import modified its source")
        finally:
            QFileDialog.getOpenFileName = original
            window.preferences = old
            save_preferences(old)
            QApplication.instance().setFont(font)
            window.apply_preferences()

    check("documented_tle_settings_font_theme_date_format_and_details", settings)
