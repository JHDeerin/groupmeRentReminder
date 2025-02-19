#!/usr/bin/env python3
"""
A quick script to create a GroupMe bot and have it send a reminder message to
our apartment's GroupMe about the rent
"""

import os
import re
import traceback
from datetime import datetime, timedelta

import fastapi
import requests
from pydantic import BaseModel

from . import sheet
from .getRents import get_current_charges
from .sheet import GoogleSheet

TOKEN = os.environ.get("GROUPME_TOKEN")
BOT_ID = os.environ["GROUPME_BOT_ID"]
BOT_NAME = "RentBot"
LANDLORD_GROUPME_NAME = "Jake Deerin"
LANDLORD_VENMO = "https://venmo.com/Jake-Deerin"
LANDLORD_PAYPAL = "https://paypal.me/jhdeerin"
REMINDER_MESSAGE = f'It\'s RENT TIME again for the month!\n\nIn a few minutes, rents will be posted and you can type "/rent show" to see how much you owe @{LANDLORD_GROUPME_NAME}'
HELP_MESSAGE = """Hey! You can make me do things by typing "/rent <command name>" (without the quotes); here're the available commands:

"/rent show"
    Show how much everyone owes right now + how to pay
"/rent weeks-stayed <num weeks>"
    (Deprecated) Mark how long you've stayed this month, e.g. "/rent weeks-stayed 4"
"/rent paid"
    Mark that you've paid this month's rent
"/rent add <GroupMe user name>"
    Add someone new (you, by default) to pay the rent
"/rent remove <GroupMe user name>"
    Removes someone (you, by default) from paying rent
"/rent rent-amt <rent cost>"
    Set the total apartment rent for the month
"/rent utility-amt <rent cost>"
    Set the total apartment utility bill for the month
"/rent help"
    Have this chit-chat with me again, anytime

If you need more info, you can poke around my insides here: https://github.com/JHDeerin/rentbot
"""


app = fastapi.FastAPI()
googleSheetConnection = GoogleSheet()


def listGroups(token: str) -> str:
    url = f"https://api.groupme.com/v3/groups?token={token}&per_page=499"
    result = requests.get(url)
    groups = result.json()["response"]
    groupInfo = []
    for group in groups:
        groupInfo.append(f"{group['name']} - {group['id']}")
    return "\n".join(groupInfo)


def createBot(
    token: str,
    groupID: str = "52458108",
    botName: str = BOT_NAME,
    imageURL: str = "https://p.kindpng.com/picc/s/47-476269_cute-clock-png-clip-art-for-kids-clipart.png",
):
    botCreationJSON = {
        "bot": {"name": botName, "group_id": groupID, "avatar_url": imageURL}
    }
    url = f"https://api.groupme.com/v3/bots?token={token}"
    result = requests.post(url, json=botCreationJSON)
    return result.json()


def sendBotMessage(botID: str, message: str):
    body = {"bot_id": botID, "text": message}
    result = requests.post("https://api.groupme.com/v3/bots/post", json=body)
    return result.text


def getDefaultTimeForCommand() -> datetime:
    """
    Returns the default time you should use for the current command (basically
    2 weeks ago, but you should only use the year/month to make decisions)
    """
    time = datetime.utcnow() - timedelta(days=14)
    return time


class BotCommand:
    def __init__(self, cmdName: str = ""):
        self.botTrigger = r"^\s*/rent\s+"
        self.cmdRegex = re.compile(f"{self.botTrigger}{cmdName}")
        self.cmdName = cmdName

    def isCommand(self, userInput: str):
        return re.search(self.cmdRegex, userInput)

    def execute(self, userInput: str, userName: str = ""):
        pass


class HelpCommand(BotCommand):
    def __init__(self):
        super().__init__(cmdName="help")

    def execute(self, userInput: str, userName: str = ""):
        sendBotMessage(BOT_ID, HELP_MESSAGE)


class AddCommand(BotCommand):
    def __init__(self):
        super().__init__(cmdName="add")
        self.userNameRegex = re.compile(f"{self.cmdRegex.pattern}\s+@?(.+)")

    def getCommandedUser(self, userInput: str) -> str:
        matches = self.userNameRegex.search(userInput)
        if not matches:
            return ""

        user = matches.group(1)
        return user

    def execute(self, userInput: str, userName: str = ""):
        userToAdd = self.getCommandedUser(userInput)
        if not userToAdd:
            userToAdd = userName
        googleSheetConnection.addTenant(userToAdd, getDefaultTimeForCommand())
        sendBotMessage(BOT_ID, f"Added @{userToAdd} to the rent roll")


class RemoveCommand(BotCommand):
    def __init__(self):
        super().__init__(cmdName="remove")
        self.userNameRegex = re.compile(f"{self.cmdRegex.pattern}\s+@?(.+)")

    def getCommandedUser(self, userInput: str) -> str:
        matches = self.userNameRegex.search(userInput)
        if not matches:
            return ""

        user = matches.group(1)
        return user

    def execute(self, userInput: str, userName: str = ""):
        userToRemove = self.getCommandedUser(userInput)
        if not userToRemove:
            userToRemove = userName
        googleSheetConnection.removeTenant(userToRemove, getDefaultTimeForCommand())
        sendBotMessage(BOT_ID, f"Removed @{userToRemove} from the rent roll")


class PaidCommand(BotCommand):
    def __init__(self):
        super().__init__(cmdName="paid")
        self.parseCostRegex = re.compile(f"{self.cmdRegex.pattern}\s+()(\d*\.?\d+)")

    def execute(self, userInput: str, userName: str = ""):
        time = getDefaultTimeForCommand()
        try:
            googleSheetConnection.markRentAsPaid(userName, time)
        except sheet.MonthNotFoundError:
            # Try going backwards 1 month; maybe the current month's data isn't
            # available yet and they intended to pay for the last month
            # TODO: Find a more robust/general solution, like specifying the
            # month you want to pay for
            time = time - timedelta(days=30)
            googleSheetConnection.markRentAsPaid(userName, time)
        monthStr = time.strftime("%B")
        sendBotMessage(BOT_ID, f"@{userName} paid the rent for {monthStr} {time.year}")


class RentAmtCommand(BotCommand):
    def __init__(self):
        super().__init__(cmdName="rent-amt")
        self.parseCostRegex = re.compile(f"{self.cmdRegex.pattern}\s+\$?(\d*\.?\d+)")

    def execute(self, userInput: str, userName: str = ""):
        matches = self.parseCostRegex.search(userInput)
        if not matches:
            sendBotMessage(
                BOT_ID,
                'Hmmm, I couldn\'t read that amount (did you include it like "/rent rent-amt $1234.00"?)',
            )
            return

        totalRent = float(matches.group(1))
        print(totalRent)
        time = getDefaultTimeForCommand()
        googleSheetConnection.setTotalRent(totalRent, time)

        monthStr = time.strftime("%B")
        sendBotMessage(
            BOT_ID,
            f"@{userName} set the total bill for {monthStr} {time.year} at ${totalRent:.2f}",
        )


class UtilityAmtCommand(BotCommand):
    def __init__(self):
        super().__init__(cmdName="utility-amt")
        # TODO: Try to reuse this pattern?
        self.parseCostRegex = re.compile(f"{self.cmdRegex.pattern}\s+\$?(\d*\.?\d+)")

    def execute(self, userInput: str, userName: str = ""):
        matches = self.parseCostRegex.search(userInput)
        if not matches:
            sendBotMessage(
                BOT_ID,
                'Hmmm, I couldn\'t read that amount (did you include it like "/rent utility-amt $1234.00"?)',
            )
            return

        totalUtility = float(matches.group(1))
        print(totalUtility)
        time = getDefaultTimeForCommand()
        googleSheetConnection.setTotalUtility(totalUtility, time)

        monthStr = time.strftime("%B")
        sendBotMessage(
            BOT_ID,
            f"@{userName} set the total utility cost for {monthStr} {time.year} to ${totalUtility:.2f}",
        )


class WeeksStayedCommand(BotCommand):
    def __init__(self):
        super().__init__(cmdName="weeks-stayed")
        # TODO: Try to reuse this pattern?
        self.parseWeeksRegex = re.compile(f"{self.cmdRegex.pattern}\s+(\d*\.?\d+)")

    def execute(self, userInput: str, userName: str = ""):
        matches = self.parseWeeksRegex.search(userInput)
        if not matches:
            sendBotMessage(
                BOT_ID,
                'Hmmm, I couldn\'t read how many weeks that was (did you include it like "/rent weeks-stayed 4"?)',
            )
            return

        weeksStr = matches.group(1)
        weeks = float(weeksStr)
        print(weeks)
        time = getDefaultTimeForCommand()
        googleSheetConnection.setWeeksStayed(weeks, userName, time)

        monthStr = time.strftime("%B")
        sendBotMessage(
            BOT_ID, f"@{userName} stayed for {weeksStr} weeks in {monthStr} {time.year}"
        )


class ShowCommand(BotCommand):
    def __init__(self):
        super().__init__(cmdName="show")

    def execute(self, userInput: str, userName: str = ""):
        amountsOwed = googleSheetConnection.getAmountsOwed()
        print(f"Amounts owed: {amountsOwed}")
        if amountsOwed:
            owedStrings = "\n".join(
                sorted([f"@{name}: ${amt:.2f}" for name, amt in amountsOwed.items()])
            )
        else:
            owedStrings = "...hmmm, I'm not sure who's paying rent right now (have you run \"/rent add\" to add yourself?)"
        fullMessage = f"=== Rents Due ===\n{owedStrings}\n\nVenmo: {LANDLORD_VENMO}\nPayPal: {LANDLORD_PAYPAL}\nSpreadsheet for audits: {sheet.SHEETS_URL}"
        sendBotMessage(BOT_ID, fullMessage)


class GroupMeMessage(BaseModel):
    text: str
    name: str


@app.post("/")
def parseGroupMeMessage(msg: GroupMeMessage):
    msgText = msg.text
    msgUser = msg.name

    if not BotCommand().isCommand(msgText):
        return "Not a RentBot command", 200

    print(f'Received message "{msgText}" from "{msgUser}"')

    commands = [
        HelpCommand(),
        AddCommand(),
        RemoveCommand(),
        PaidCommand(),
        RentAmtCommand(),
        UtilityAmtCommand(),
        WeeksStayedCommand(),
        ShowCommand(),
    ]
    for cmd in commands:
        if cmd.isCommand(msgText):
            print(f"{cmd.cmdName} triggered")
            try:
                cmd.execute(msgText, msgUser)
            except Exception:
                print(traceback.format_exc())
                sendBotMessage(
                    BOT_ID,
                    "🤒 Oh no - I'm feeling sick right now! Please try again when I'm feeling better (we'll send someone to patch me up)",
                )
                return "Internal server error", 500
            return "Parsed message successfully", 200

    sendBotMessage(
        BOT_ID, 'Hmmm, I don\'t recognize that command (try typing "/rent help"?)'
    )
    return f'Unrecognized command "{msgText}"', 400


def _cents_to_dollar_str(cents: int) -> str:
    return f"${cents / 100:.2f}"


def _getCurrentRents():
    print("Getting charges for the current month in the background")
    get_current_charges(verbose=True)
    print("Got the charges")


def _setCurrentRents():
    print("Getting charges for the current month in the background")
    charges = get_current_charges(verbose=True)
    print("Got the charges; setting them now...")
    rcmd = RentAmtCommand()
    rcmd.execute(
        userInput=f"/rent {rcmd.cmdName} {_cents_to_dollar_str(charges.rent_cents)}",
        userName=BOT_NAME,
    )
    ucmd = UtilityAmtCommand()
    ucmd.execute(
        userInput=f"/rent {ucmd.cmdName} {_cents_to_dollar_str(charges.utilities_cents)}",
        userName=BOT_NAME,
    )
    scmd = ShowCommand()
    scmd.execute(userInput=f"/rent {scmd.cmdName}", userName=BOT_NAME)


@app.get("/reminder")
def remindGroup(tasks: fastapi.BackgroundTasks):
    """
    Posts a reminder to pay the rent to the GroupMe
    """
    print("Received reminder request")
    googleSheetConnection.createNewMonth(getDefaultTimeForCommand())
    print(f"Made sure month data exists for {getDefaultTimeForCommand().isoformat()}")
    sendBotMessage(BOT_ID, REMINDER_MESSAGE)
    tasks.add_task(_setCurrentRents)
    return "Reminder message sent", 200


@app.get("/test/getRents")
def testGetRents(tasks: fastapi.BackgroundTasks):
    """
    Tests getting the current rents in the background silently, i.e. without
    sending any GroupMe messages
    """
    print("Received /test/getRents request")
    tasks.add_task(_getCurrentRents)
    return "Test initiated", 200
