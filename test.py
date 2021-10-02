from sheet import GoogleSheet, MonthData, MonthlyTenant
import pytest


googleSheetConnection = GoogleSheet()


@pytest.fixture
def unpaidSeptemberNoRentPosted() -> MonthData:
    return MonthData(year=2021, month=9, totalRent=0.0, totalUtility=0.0, tenants={
        'Mac Mathis': MonthlyTenant(name='Mac Mathis', weeksStayed=4.0, isPaid=False),
        'Jake Deerin': MonthlyTenant(name='Jake Deerin', weeksStayed=4.0, isPaid=False),
        'Taylor Daniel': MonthlyTenant(name='Taylor Daniel', weeksStayed=0.0, isPaid=False),
        'Andrew Dallas': MonthlyTenant(name='Andrew Dallas', weeksStayed=0.0, isPaid=False),
        'Andrew Wittenmyer': MonthlyTenant(name='Andrew Wittenmyer', weeksStayed=0.0, isPaid=False),
        'Josh Minter':MonthlyTenant(name='Josh Minter', weeksStayed=4.0, isPaid=False),
        'David Deerin': MonthlyTenant(name='David Deerin', weeksStayed=0.0, isPaid=False),
        'Manny Jonson': MonthlyTenant(name='Manny Jonson', weeksStayed=4.0, isPaid=False)
    })


@pytest.fixture
def partiallyPaidAugustRent() -> MonthData:
    return MonthData(year=2021, month=8, totalRent=1697.0, totalUtility=413.18, tenants={
        'Mac Mathis': MonthlyTenant(name='Mac Mathis', weeksStayed=4.0, isPaid=True),
        'Jake Deerin': MonthlyTenant(name='Jake Deerin', weeksStayed=4.0, isPaid=True),
        'Taylor Daniel': MonthlyTenant(name='Taylor Daniel', weeksStayed=2.0,isPaid=True),
        'Andrew Dallas': MonthlyTenant(name='Andrew Dallas', weeksStayed=4.0, isPaid=True),
        'Andrew Wittenmyer': MonthlyTenant(name='Andrew Wittenmyer', weeksStayed=2.0, isPaid=False),
        'Josh Minter': MonthlyTenant(name='Josh Minter', weeksStayed=4.0, isPaid=True),
        'David Deerin': MonthlyTenant(name='David Deerin', weeksStayed=1.0, isPaid=False),
        'Manny Jonson': MonthlyTenant(name='Manny Jonson', weeksStayed=2.0, isPaid=False)
    })


def testNoTotalRentHasNoCharges(unpaidSeptemberNoRentPosted):
    expected = {'Mac Mathis': 0.0, 'Jake Deerin': 0.0, 'Taylor Daniel': 0.0, 'Andrew Dallas': 0.0, 'Andrew Wittenmyer': 0.0, 'Josh Minter': 0.0, 'David Deerin': 0.0, 'Manny Jonson': 0.0}

    monthAmountsOwed = googleSheetConnection._getAmountsOwedForMonth(unpaidSeptemberNoRentPosted)
    assert monthAmountsOwed == expected


def testPartiallyPaidMonthCharges(partiallyPaidAugustRent):
    expected = {'Andrew Wittenmyer': 183.49391304347824, 'David Deerin': 91.74695652173912, 'Manny Jonson': 183.49391304347824}

    monthAmountsOwed = googleSheetConnection._getAmountsOwedForMonth(partiallyPaidAugustRent)
    assert monthAmountsOwed == expected
