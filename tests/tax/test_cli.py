from eco_model.tax.cli import main_tax


def test_cli_prints_markdown_explanation(capsys):
    code = main_tax(
        ["--dob", "2004-06-15", "--salary", "52000", "--pay-frequency", "fortnightly",
         "--tax-year", "2028", "--allow-assumed"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("# ")
    assert "8008.00" in out


def test_cli_without_opt_in_reports_error(capsys):
    code = main_tax(["--dob", "2004-06-15", "--salary", "52000", "--tax-year", "2028"])
    assert code == 2
    assert "allow-assumed" in capsys.readouterr().err


def test_cli_with_extra_income_and_loan(capsys):
    code = main_tax(
        ["--dob", "2004-06-15", "--salary", "52000", "--tax-year", "2027", "--student-loan",
         "--kiwisaver-rate", "0.03", "--self-employment", "1000", "--other-income", "500",
         "--include-self-employment"]
    )
    assert code == 0
    assert "student_loan_repayment" in capsys.readouterr().out


def test_cli_aggregate_flag(capsys):
    code = main_tax(["--aggregate"])
    assert code == 0
    assert "not_estimable_from_public_aggregates" in capsys.readouterr().out


def test_cli_missing_required_args(capsys):
    assert main_tax(["--salary", "1"]) == 2
