# Dailies bot by Grant Scrits 
#        @GeekOverdriveUS

import discord
from discord.ext import commands
from discord.ext.commands import Bot
from discord.ext.commands import CommandNotFound
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import requests
from datetime import datetime, timedelta
from dateutil import tz
from calendar import monthrange
import operator
import time
import math
from enum import Enum
import random
import json
import os
import sys
import traceback

from dotenv import load_dotenv
load_dotenv()
BOT_ID = os.getenv("DISCORD_TOKEN")

# Switched to Ints to comply with new Discord.py conventions for IDs
DAILY_CHANNEL_ID = int(os.getenv("DAILY_CHANNEL_ID"))
DDISC_CHANNEL_ID = int(os.getenv("DDISC_CHANNEL_ID"))
SPAM_CHANNEL_ID  = int(os.getenv("SPAM_CHANNEL_ID"))
STREAKER_NOTIFY_ID = int(os.getenv("STREAKER_NOTIFY_ID"))

API_HOST = os.getenv("API_HOST", "http://localhost:42069")

API = {
    "getURL": API_HOST + "/api/v0/discord/embedtemplate",
    "postURL": API_HOST + "/api/v0/dailies/version"
}

class Streaker:
    def __init__(self, id, name=None, days={}, lpt=None, streak=1, weekStreak=0, streakRecord=0, streakAllTime=0, mercies=0, casual = False, lowMercyWarn = True, vacationMode = (False, datetime.utcnow()-timedelta(2))):
        self.id = id
        self.name = name
        if (lpt): self.lastPostTime = lpt
        else:     self.lastPostTime = datetime.utcnow()
        self.streak = streak
        self.weekStreak = weekStreak
        self.streakRecord = streakRecord
        self.streakAllTime = streakAllTime
        self.mercies = mercies
        self.casual = casual # Parry this you filthy casual
        self.lowMercyWarn = lowMercyWarn
        self.days = days
        self.vacationMode = vacationMode
    
    def BumpStreak(self):
        self.streak += 1
        self.streakAllTime += 1
        self.lastPostTime = datetime.utcnow()
        if (self.streak > self.streakRecord): self.streakRecord = self.streak

        if (self.casual):
            self.weekStreak += 1
        elif (self.streak % 3 == 0 and self.mercies < 30):
            self.mercies += 1
        backup()

    def AddDay(self, postID):
        self.days[str(self.streak)] = postID

    def ResetStreak(self):
        self.streak = 0
        self.weekStreak = 0
        self.lastPostTime = None
        backup()


class Milestone(Enum):
    Loss = 0
    New = 1
    ThreeDay = 2
    Week = 3
    Month = 4
    Year = 5
    Mercy = 6
    CasualOneThird = 7
    CasualTwoThirds = 8
    CasualThreeThirds = 9

    def __lt__(self, other):
        return self.value < other.value

streakers = []
streakMilestones = {}
lastDay = 0
lastLBMessage = None
lastCMDMessage = None

bot = commands.Bot(command_prefix='!')
bot.remove_command("help")

def main():
    global lastDay

    lastDay = datetime.utcnow().day
    load_backup()

    bot.run(BOT_ID)


@bot.event
async def on_ready():

    # This is all a nice simple hack to improvise a version control system out of the streak user system
    # -[
    version = "1.64.1"
    send_version_message = True

    version_message = """
:vertical_traffic_light: :wrench: Bug Fix:

:beetle: Vacation Mode works properly now and won't use up your Mercy Days
:tools: When Vacation Mode is enabled, it is now visible streak tooltips
:sparkles: Streak tooltips now have icons
"""

    found_update_user = False
    for s in streakers:
        if (s.name == version):
            found_update_user = True

    if (not found_update_user):
        if (send_version_message):
            await bot.get_channel(DAILY_CHANNEL_ID).send(version_message)
        streakers.append(Streaker(1, version, streak=0))
        backup()

    # ]-

    url = API["postURL"] + "?version={}".format(version)
    print(url)
    try: requests.post(url)
    except Exception: print("\n*UNABLE TO SEND VERSION TO API*")

    print("\nDailies bot at the ready!")

    # await bot.change_presence(activity=discord.Game(name="Maintaining Streaks"))



@bot.event
async def on_message(msg):
    await bot.process_commands(msg)

    if (msg.author.id == bot.user.id):
        return

    if (msg.channel.id == DAILY_CHANNEL_ID): await processStreakMsg(msg)
    await processEndOfDay(msg)


async def processStreakMsg(msg):
    # Get message
    # Check for streaker ID
    # Add streaker if no ID is found
    # Update streak
    global lastDay

    streaker = getStreaker(msg.author.id)

    if (streaker):
        # If this user was found in the local database...
        # If this user has already posted today, ignore it
        # Unless this is the rollover-causing streaker (today != lastDay)
        if (streaker.vacationMode[0]):
            await msg.add_reaction('⚠️')
            await bot.get_channel(DDISC_CHANNEL_ID).send(":warning: {} ` You need to disable Vacation Mode to continue your streak! Use '!vacation'`".format(msg.author.mention))
            return

        if (dayDifferenceNow(streaker.lastPostTime) < 1 and datetime.utcnow().day == lastDay):
            await msg.add_reaction('💯')
            return
        else:
            streaker.lastPostTime = datetime.utcnow() - timedelta(hours = 1)

        # Update streak and react
        streaker.BumpStreak()
        streaker.AddDay(msg.id)
        await reactToStreak(streaker, msg)
    else:
        # If this user was not found, add them to the database
        await msg.add_reaction('❤️')

        info = await bot.fetch_user(msg.author.id)
        if len(info.display_name.split()) > 1:
            name = info.display_name.title()
        else:
            name = info.display_name

        streakers.append(Streaker(msg.author.id, name, { "1": msg.id })); backup()
        await bot.get_channel(DDISC_CHANNEL_ID).send(":white_check_mark: `{} has started their first streak!`".format(name))


async def reactToStreak(s, msg):
    if not s.casual:
        if (s.streak % 30 == 0):
            await msg.add_reaction('🔥')
        elif (s.streak % 7 == 0):
            await msg.add_reaction('🔱')
        elif (s.streak % 3 == 0):
            await msg.add_reaction('⚜️')
        else:
            await msg.add_reaction('❤️')
    else:
        if s.weekStreak < 3:
            await msg.add_reaction('⚜️')
        elif s.weekStreak < 5:
            await msg.add_reaction('🔱')
        else:
            await msg.add_reaction('🔥')


async def processEndOfDay(msg, test = False):
    global lastDay
    global streakMilestones
    newDay = False
    newWeek = False
    newMonth = False
    if (datetime.utcnow().day != lastDay or test):
        newDay = True
        if not test:
            lastDay = datetime.utcnow().day
            # If yesterday's week is not the same as today's week...
            if ( (datetime.utcnow() - timedelta(1)).isocalendar()[1] != datetime.utcnow().isocalendar()[1] ): newWeek = True
            # If yesterday's month is not the same as today's month...
            if ( (datetime.utcnow() - timedelta(1)).month != datetime.utcnow().month ): newMonth = True
        else:
            newMonth = True
            newWeek = True
        await bot.get_channel(DAILY_CHANNEL_ID).send(":vertical_traffic_light: `A new streak day has started ( Time in UTC is: {0} )` <@&{1}>".format(datetime.utcnow(), STREAKER_NOTIFY_ID))

    if newDay:
        for s in streakers:
            specialMilestone = False
            # If this streaker has a null name field, populate it with their username
            if (not s.name):
                info = await bot.fetch_user(s.id)
                if len(info.display_name.split()) > 1:
                    name = info.display_name.title()
                else:
                    s.name = info.display_name

            # if the time since this (Challenge Mode) streaker's last post is more than one day
            if not s.casual and not s.vacationMode[0] and s.streak != 0 and dayDifferenceNow(s.lastPostTime) > 1:
                # If this streaker is the rollover-causing author, adjust their post time backward by 1hr so that it doesn't count towards the new day
                if (s.id == msg.author.id and msg.channel.id == DAILY_CHANNEL_ID): 
                    s.lastPostTime = datetime.utcnow() - timedelta(hours = 1)
                else:
                    specialMilestone = True
                    if (s.mercies == 0):
                        streakMilestones[s.id] = [Milestone.Loss, s.streak]
                        s.ResetStreak()
                    else:
                        streakMilestones[s.id] = [Milestone.Mercy, s.streak]
                        s.mercies -= 1; backup()

                        if (s.mercies < 2 and s.lowMercyWarn):
                            try:
                                user = await bot.fetch_user(s.id)
                                await user.send("Your streak is going to expire in **{0} {2}**. You have **{1} Mercy Days** left!\nMake sure to post something in `#daily-challenge` before then.\n\nUse `!toggleWarnings` to turn this notification off.".format(s.mercies + 1, s.mercies, "Days" if (s.mercies + 1 > 1) else "Day"))
                            except Exception as e:
                                print("\n{} COULDN'T BE MESSAGED! THEIR STREAK IS ABOUT TO EXPIRE!!!\n".format(s.name))

            if (s.streak != 0 and not specialMilestone):
                if not s.casual:
                    if (s.streak == 1):
                        streakMilestones[s.id] = [Milestone.New, s.streak]
                    elif (s.streak % 365 == 0):
                        streakMilestones[s.id] = [Milestone.Year, s.streak]
                    elif (s.streak % 30 == 0):
                        streakMilestones[s.id] = [Milestone.Month, s.streak]
                    elif (s.streak % 7 == 0):
                        streakMilestones[s.id] = [Milestone.Week, s.streak]
                    elif (s.streak % 3 == 0):
                        streakMilestones[s.id] = [Milestone.ThreeDay, s.streak]
                else:
                    if newWeek and not newMonth:
                        if s.weekStreak < 3:
                            streakMilestones[s.id] = [Milestone.CasualOneThird, s.weekStreak]
                        elif s.weekStreak < 5:
                            streakMilestones[s.id] = [Milestone.CasualTwoThirds, s.weekStreak]
                        else:
                            streakMilestones[s.id] = [Milestone.CasualThreeThirds, s.weekStreak]
                        s.weekStreak = 0
                    elif newMonth:
                        if s.streak < 10:
                            streakMilestones[s.id] = [Milestone.CasualOneThird, s.streak]
                        elif s.streak < 20:
                            streakMilestones[s.id] = [Milestone.CasualTwoThirds, s.streak]
                        else:
                            streakMilestones[s.id] = [Milestone.CasualThreeThirds, s.streak]
                        s.streak = 0

        await sendMilestones(streakMilestones, newMonth)
        streakMilestones = {}


async def sendMilestones(milestones, newMonth):
    print("\nSending Milestones...")
    embeds = []
    today = datetime.utcnow().date()
    end_of_day = datetime(today.year, today.month, today.day, tzinfo=tz.tzutc()) + timedelta(1)

    challengeAlerts = []
    casualAlerts = []
    lossAlerts = []
    amazingMilestone = False
    if (len(milestones) != 0):
        # Sorted() with this configuration converts to tuple as (Streaker.id as KEY, [Milestone, Streak])
        milestonesSorted = sorted(milestones.items(), key=lambda x: x[1][0], reverse=True)
        emote = ":heart:"
        milestone = 0
        milestonePeriod = "DAY"
        for keyPair in milestonesSorted:
            casual = False
            if (keyPair[1][0] in [Milestone.CasualOneThird, Milestone.CasualTwoThirds, Milestone.CasualThreeThirds]): casual = True
            milestone = keyPair[1][1]

            if (keyPair[1][0] == Milestone.Mercy):
                emote = ":revolving_hearts:"
                milestonePeriod = "DAY"
            elif (keyPair[1][0] == Milestone.Loss):
                emote = ":100:"
                milestonePeriod = "DAY"
            elif (keyPair[1][0] == Milestone.New):
                emote = ":beginner:"
                milestonePeriod = "DAY"
            elif (keyPair[1][0] == Milestone.Year):
                emote = ":bangbang: :interrobang:"
                milestone = keyPair[1][1] // 365
                milestonePeriod = "YEAR"
                amazingMilestone = True
            elif (keyPair[1][0] == Milestone.Month):
                emote = ":fire:"
                milestone = keyPair[1][1] // 30
                milestonePeriod = "MONTH"
                amazingMilestone = True
            elif (keyPair[1][0] == Milestone.Week):
                emote = ":trident:"
                milestone = keyPair[1][1] // 7
                milestonePeriod = "WEEK"
            elif (keyPair[1][0] == Milestone.ThreeDay):
                emote = ":fleur_de_lis:"
                milestonePeriod = "DAY"
            elif (keyPair[1][0] == Milestone.CasualThreeThirds):
                emote = ":fire:"
                milestonePeriod = "DAY"
            elif (keyPair[1][0] == Milestone.CasualTwoThirds):
                emote = ":trident:"
                milestonePeriod = "DAY"
            elif (keyPair[1][0] == Milestone.CasualOneThird):
                emote = ":fleur_de_lis:"
                milestonePeriod = "DAY"
            
            # Make period plural if milestone is more than one
            milestonePeriod += "S" if milestone != 1 else ""
            streaker = getStreaker(keyPair[0])
            if (keyPair[1][0] in [Milestone.ThreeDay, Milestone.Week, Milestone.Month, Milestone.Year]):
                challengeAlerts.append("\n{0} `{1} has achieved a streak of` **{2} {3}**".format(emote, streaker.name, milestone, milestonePeriod))
            elif (keyPair[1][0] == Milestone.Loss):
                lossAlerts.append("\n{0} `{1} achieved a streak of` **{2} {3}**".format(emote, streaker.name, milestone, milestonePeriod))
            elif (keyPair[1][0] == Milestone.New):
                challengeAlerts.append("\n{0} `{1} has started a new streak!`".format(emote, streaker.name))
            elif (keyPair[1][0] == Milestone.Mercy):
                challengeAlerts.append("\n{0} `{1}'s streak of` **{2} {3}** `was saved by a Mercy Day!`".format(emote, streaker.name, milestone, milestonePeriod))
            elif keyPair[1][0] in [Milestone.CasualOneThird, Milestone.CasualTwoThirds, Milestone.CasualThreeThirds]:
                casualAlerts.append("\n{0} `{1} achieved a streak of` **{2} {3}** `this {4}`".format(emote, streaker.name, milestone, milestonePeriod, "MONTH" if newMonth else "WEEK"))
        
        fields = []
        thisField = -1

        if (len(challengeAlerts) > 0):
            fields.append({
                "name": "Milestones",
                "value": ""
            })
            thisField += 1
            for line in challengeAlerts:
                if len(fields[thisField]["value"]) > 900:
                    fields.append({
                        "name": "Milestones",
                        "value": ""
                    })
                    thisField += 1
                fields[thisField]["value"] += line
        else: print("No Milestones")

        if (len(casualAlerts) > 0):
            fields.append({
                "name": "Casual Milestones",
                "value": ""
            })
            thisField += 1
            for line in casualAlerts:
                if len(fields[thisField]["value"]) > 900:
                    fields.append({
                        "name": "Casual Milestones",
                        "value": ""
                    })
                    thisField += 1
                fields[thisField]["value"] += line
        else: print("No Casual Milestones")

        if (len(lossAlerts) > 0):
            fields.append({
                "name": "Losses",
                "value": ""
            })
            thisField += 1
            for line in lossAlerts:
                if len(fields[thisField]["value"]) > 900:
                    fields.append({
                        "name": "Losses",
                        "value": ""
                    })
                    thisField += 1
                fields[thisField]["value"] += line
        else: print("No Losses")

        embedCharacterLength = 0
        thisEmbed = 0
        # If we have any alerts, checked by seeing that we incremented thisField
        if (thisField > -1):
            embedData = getEmbedData()
            embeds.append(discord.Embed(color=embedData["color"]))
            embeds[thisEmbed].set_footer(text="Next Streak Day:", icon_url=embedData["footer"]["icon_url"])
            embeds[thisEmbed].timestamp = end_of_day

            for field in fields:
                if (embedCharacterLength > 5000):
                    embedCharacterLength = 0
                    thisEmbed += 1
                    embeds.append(discord.Embed(color=getEmbedData()["color"]))
                embeds[thisEmbed].add_field(name=field["name"], value=field["value"], inline=False)
                embedCharacterLength += len(field["value"])
        # Thought about adding this as a thumbnail to the first embed, but it's too dang small to notice
        if (amazingMilestone):
            await bot.get_channel(DAILY_CHANNEL_ID).send(file=discord.File('assets/amazingStreak.gif'))
        try:
            for e in embeds:
                # skip empty embeds (shouldn't happen, but it does pretty rarely)
                if (len(e.fields) == 0): continue
                await bot.get_channel(DAILY_CHANNEL_ID).send(embed=e)
        except Exception:
            # This ugly thing logs the nitty-gritty details of the embeds and fields. This should allow me to pinpoint exactly what is going wrong when it next chucks a fastball
            print("\n* ERROR SUBMITTING MILESTONES *\n")
            error = traceback.format_exc()
            embed_str = []
            eCount = 0
            for e in embeds:
                embed_str.append("EMBED {}\n".format(eCount))
                for f in e.fields:
                    for line in str(f).split("\\n"):
                        embed_str.append(line + "\n")
                embed_str.append(str(e.footer) + "\n")
                eCount += 1
            field_str = []
            for f in fields:
                for line in str(f).split("\\n"):
                    field_str.append(line + "\n")
            with open("data/log.txt", "w") as log_file:
                log_file.write("ERROR:\n{}".format(error))
                log_file.write("\n\nEMBEDS:\n")
                log_file.writelines(embed_str)
                log_file.write("\n\nFIELDS:\n")
                log_file.writelines(field_str)

    else:
        print("...no milestones to send\n")



#
#
# USER COMMANDS
#
#

@bot.command(
    brief="Shorthand for !streaks"
)
async def s(ctx, extra = None):
    await streaks(ctx, extra)

@bot.command(
    brief="Shorthand for !streaks"
)
async def streak(ctx, extra = None):
    await streaks(ctx, extra)

@bot.command(
    brief="Show streak stats of the target user",
    description="""(target) : 'target' is optional. If left out, it defaults to you. This value can be entered as 'me', 'top', 'all', a user ID, or nothing. 'me' shows your streak stats. 'top' shows the top three streak groups and the users in them. 'all' shows all of the streak groups.

This command will show you the streak stats of the target user"""
)
async def streaks(ctx, extra = None):
    global lastLBMessage
    global lastCMDMessage
    has_alerted_wait = False

    today = datetime.utcnow().date()
    end_of_day = datetime(today.year, today.month, today.day, tzinfo=tz.tzutc()) + timedelta(1)

    embedData = getEmbedData()
    embed = discord.Embed(title="STREAKS", description="", color=embedData["color"])
    embed.set_footer(text=embedData["footer"]["text"] + "\nNext Streak Day:", icon_url=embedData["footer"]["icon_url"])
    embed.timestamp = end_of_day

    if (not extra or extra.lower() == "me"):
        streakUser = None
        for s in streakers:
            if (s.id == ctx.message.author.id):
                streakUser = s
                break

        user = await bot.fetch_user(ctx.message.author.id)
        embed.set_author(name = user.display_name, icon_url=user.avatar_url)

        if (streakUser):
            # If the user's name has not been added to the class (Done to make compatible with pre 6/3/2020 data backups)
            # Now used to update names in the list to adapt to user nickname changes
            #--if not s.name:
            if len(user.display_name.split()) > 1:
                s.name = user.display_name.title()
            else:
                s.name = user.display_name

            if streakUser.vacationMode[0]: embed.title = ":beach: Vacation Mode"
            else: embed.title=":crossed_swords: Challenge Mode" if not streakUser.casual else ":shield: Casual Mode"

            if (not streakUser.casual):
                # Uhg, this mess
                if (streakUser.streak > 1): day1 = "DAYS"
                elif (streakUser.streak > 0): day1 = "DAY"
                else: day1 = ""
                embed.description="Current Streak: **{0} {4}**\nMercy Days: **{1}**\n\n`Highest Streak:` {2}\n`Streak Day Total:` {3}".format(streakUser.streak, streakUser.mercies, streakUser.streakRecord, streakUser.streakAllTime, day1)
            else:
                # UHGGGG
                if (streakUser.streak > 1): day1 = "DAYS"
                elif (streakUser.streak > 0): day1 = "DAY"
                else: day1 = ""
                if (streakUser.weekStreak > 1): day2 = "DAYS"
                elif (streakUser.weekStreak > 0): day2 = "DAY"
                else: day2 = ""
                embed.description="Current Month Streak: **{0} {4}**\nCurrent Week Streak: **{1} {5}**\n\n`Highest Streak: {2}\nStreak Day Total: {3}`".format(streakUser.streak, streakUser.weekStreak, streakUser.streakRecord, streakUser.streakAllTime, day1, day2)
        else:
            embed.title="Clothist Mode"
            embed.description="You do not have a streak. Start one in {}".format(bot.get_channel(DAILY_CHANNEL_ID).name)

    elif (extra.lower() == "all"):
        if (ctx.message.channel.id != SPAM_CHANNEL_ID):
            await ctx.send(":x: `-!streaks all- can only be used in {}`".format(bot.get_channel(SPAM_CHANNEL_ID).name))
            return
        else:
            embed.title="STREAKS"
            embed.description="---------------------------------------------------------------------"

            streakGroups = getStreakGroups()
            noStreakers = True
            for group in streakGroups:
                names = ""
                for s in streakers:
                    if (s.streak == group):
                        noStreakers = False

                        if not s.name: # If the user's name has not been added to the class (Done to make compatible with pre 6/3/2020 data backups)
                            if not has_alerted_wait:
                                has_alerted_wait = True
                                await ctx.send(":stopwatch: `Please allow me a minute to assemble the list for you`")
                            user = await bot.fetch_user(s.id)
                            if len(user.display_name.split()) > 1:
                                s.name = user.display_name.title()
                            else:
                                s.name = user.display_name

                        if (names == ""):
                            names += s.name + (" (Casual)" if s.casual else "")
                        else:
                            names += "\n" + s.name + (" (Casual)" if s.casual else "")

                if (group > 1):
                    embed.add_field(name="{} DAYS".format(group), value=names, inline=True)
                else:
                    embed.add_field(name="{} DAY".format(group), value=names, inline=True)

            if (noStreakers):
                embed.description = "No streaks available at this time"

    elif (extra.lower() == "top"):
        embed.title="TOP STREAKS"
        embed.description="---------------------------------------------------------------------"

        streakGroups = getStreakGroups()
        x=0
        noStreakers = True
        for group in streakGroups:
            x+=1
            names = ""
            for s in streakers:
                if (s.streak == group):
                    noStreakers = False
                    if not s.name: # If the user's name has not been added to the class (Done to make compatible with pre 6/3/2020 data backups)
                        user = await bot.fetch_user(s.id)
                        if len(user.display_name.split()) > 1:
                            s.name = user.display_name.title()
                        else:
                            s.name = user.display_name

                    if (names == ""):
                        names += s.name
                    else:
                        names += "\n" + s.name

            if (group > 1):
                embed.add_field(name="{} DAYS".format(group), value=names, inline=True)
            else:
                embed.add_field(name="{} DAY".format(group), value=names, inline=True)

            # Cut off after displaying the third streak group
            if (x == 3):
                break

    else:
        noStreakers = False

        extra = extra.replace('<', '')
        extra = extra.replace('!', '')
        extra = extra.replace('@', '')
        extra = extra.replace('>', '')

        try:
            extra = await bot.fetch_user(extra)
            embed.set_author(name = extra.display_name, icon_url=extra.avatar_url)

            streakUser = None
            for s in streakers:
                if (s.id == extra.id):
                    streakUser = s
                    break

            if (streakUser):
                embed.title="Challenge Mode" if not streakUser.casual else "Casual Mode"
                if (not streakUser.casual):
                    # Uhg, this mess
                    if (streakUser.streak > 1): day1 = "DAYS"
                    elif (streakUser.streak > 0): day1 = "DAY"
                    else: day1 = ""
                    embed.description="Current Streak: **{0} {4}**\nMercy Days: **{1}**\n\n`Highest Streak:` {2}\n`Streak Day Total:` {3}".format(streakUser.streak, streakUser.mercies, streakUser.streakRecord, streakUser.streakAllTime, day1)
                else:
                    # UHGGGG
                    if (streakUser.streak > 1): day1 = "DAYS"
                    elif (streakUser.streak > 0): day1 = "DAY"
                    else: day1 = ""
                    if (streakUser.weekStreak > 1): day2 = "DAYS"
                    elif (streakUser.weekStreak > 0): day2 = "DAY"
                    else: day2 = ""
                    embed.description="Current Month Streak: **{0} {4}**\nCurrent Week Streak: **{1} {5}**\n\n`Highest Streak:` {2}\n`Streak Day Total:` {3}".format(streakUser.streak, streakUser.weekStreak, streakUser.streakRecord, streakUser.streakAllTime, day1, day2)
            else:
                embed.title="Clothist Mode"
                embed.description="This user does not have a streak"
        except Exception as e:
            embed.title="ERROR"
            embed.description="I couldn't find {}'s info".format(extra)
            embed.set_author(name = "", icon_url="")

    # Delete previous command responses
    if (lastCMDMessage):
        try:
            await lastCMDMessage.delete()
        except:
            pass

    if (lastLBMessage):
        try:
            await lastLBMessage.delete()
        except:
            pass

    lastCMDMessage = ctx.message
    lastLBMessage = await ctx.send(embed=embed)


@bot.command(brief="Lookup what you posted on a certain day")
async def day(ctx, day=None, user=None):
    global lastCMDMessage
    global lastLBMessage
    # Delete previous command responses
    if (lastCMDMessage):
        try:
            await lastCMDMessage.delete()
        except:
            pass

    if (lastLBMessage):
        try:
            await lastLBMessage.delete()
        except:
            pass

    # If the user wants to target a specific user...
    targetUser = getStreaker(ctx.message.author.id)
    if (user and getStreaker(user)):
        targetUser = getStreaker(user)
    # Optionally allow users to get a random post from another user by simply doing '!day <id>'
    elif (day and getStreaker(day)):
        targetUser = getStreaker(day)
        day = None
    
    try:
        iconLink = await bot.fetch_user(targetUser.id); iconLink = iconLink.avatar_url
    except:
        msg = await(ctx.send(":x: `Sorry, I couldn't find this user: {}`".format(targetUser.name)))
        await deleteInteraction((msg, ctx.message))
        return

    streakMessageId = None
    # If the user wants to find a specific streak day...
    if (day and day.isdigit()):
        for values in targetUser.days.items():
            if day in values:
                streakMessageId = values[1]
    # Else, grab a random one
    else:
        day, streakMessageId = random.choice(list(targetUser.days.items()))
    
    if (not streakMessageId):
        msg = await(ctx.send(":x: `Sorry, the post for that day wasn't found`"))
        await deleteInteraction((msg, ctx.message))
        return

    streakMessage = await bot.get_channel(DAILY_CHANNEL_ID).fetch_message(streakMessageId)

    today = datetime.utcnow().date()
    end_of_day = datetime(today.year, today.month, today.day, tzinfo=tz.tzutc()) + timedelta(1)

    embedData = getEmbedData()
    embed = discord.Embed(title="STREAK DAY {}".format(day), description=streakMessage.content, color=embedData["color"])
    embed.set_author(name=targetUser.name, icon_url=iconLink)
    embed.set_footer(text=embedData["footer"]["text"] + "\nNext Streak Day:", icon_url=embedData["footer"]["icon_url"])
    embed.timestamp = end_of_day

    if (len(streakMessage.attachments) > 0):
        embed.set_thumbnail(url=streakMessage.attachments[0].url)

    lastLBMessage = await ctx.send(embed=embed)
    await ctx.message.delete()



@bot.command(brief="Toggle casual mode",
    description="""Casual mode allows you to be a streaker without the threat of losing your streak. Your streak will instead be based on a weekly/monthly total, resetting every month.

PLEASE NOTE: Toggling this mode will reset your streak and mercy days back to 0.""")
async def casual(ctx):
    global lastCMDMessage
    global lastLBMessage
    # Delete previous command responses
    if (lastCMDMessage):
        try:
            await lastCMDMessage.delete()
        except:
            pass

    if (lastLBMessage):
        try:
            await lastLBMessage.delete()
        except:
            pass

    if (getStreaker(ctx.message.author.id)):
        s = getStreaker(ctx.message.author.id)
        if (not hasattr(s, 'casualWarn')): s.casualWarn = False
        if (not s.casualWarn):
            if not s.casual:
                lastLBMessage = await ctx.send(":warning: `Are you sure you want to enable casual mode? THIS WILL RESET YOUR STREAK AND MERCY DAYS`\n*Use* `!casual` *again to confirm.*")
            else:
                lastLBMessage = await ctx.send(":warning: `Are you sure you want to disable casual mode? THIS WILL RESET YOUR CASUAL STREAKS`\n*Use* `!casual` *again to confirm.*")
            s.casualWarn = True
            return
        
        s.casualWarn = False
        s.casual = not s.casual
        s.mercies = 0
        s.streak = 0
        s.weekStreak = 0
        backup()

        if (s.casual):
            msg = await ctx.send(":white_check_mark: `Casual Mode ENABLED. Your streak and Mercy Days have been reset`")
        else:
            msg = await ctx.send(":white_check_mark: `Casual Mode DISABLED. Remember, you start Challenge Mode with 0 Mercy Days`")
        await deleteInteraction((msg, ctx.message))
    else:
        msg = await ctx.send(":question: `You can't use this yet. Become a streaker by posting something in {} first`".format(bot.get_channel(DAILY_CHANNEL_ID).name))
        await deleteInteraction((msg, ctx.message))

@bot.command(brief="Toggle streak alerts. This role gets pinged when a new streak day starts")
async def alert(ctx):
    notifyRole = discord.utils.get(ctx.message.guild.roles, id=STREAKER_NOTIFY_ID)
    isAlerter = False
    for role in ctx.message.author.roles:
        if int(role.id) == STREAKER_NOTIFY_ID:
            isAlerter = True
            break

    try:
        if isAlerter:
            await ctx.message.author.remove_roles(notifyRole)
            await ctx.send(":white_check_mark: `New streak day alerts DISABLED`")
        else:
            await ctx.message.author.add_roles(notifyRole)
            await ctx.send(":white_check_mark: `New streak day alerts ENABLED`")
    except:
        await ctx.send(":x: `I do not have the power to modify roles!!!`")


@bot.command(brief="Toggle low Mercy Day warnings. If this is on, Pete will send you a message if your Mercy Days get low")
async def togglewarnings(ctx):
    s = getStreaker(ctx.message.author.id)
    s.lowMercyWarn = not s.lowMercyWarn; backup()

    if s.lowMercyWarn:
        await ctx.send(":white_check_mark: `You have ENABLED warnings`")
    else:
        await ctx.send(":white_check_mark: `You have DISABLED warnings`")


@bot.command(brief="Toggle vacation mode")
async def vacation(ctx):
    s = getStreaker(ctx.message.author.id)

    if s: # If streaker was found
        if not s.vacationMode[0]: # if vacation mode is not on...
            if dayDifferenceNow(s.vacationMode[1]) > 1: # if vacation mode lastChangeTime is not too recent
                s.vacationMode = (True, datetime.utcnow())
                await ctx.send(":white_check_mark: `Vacation Mode ENABLED`")
            else:
                await ctx.send(":x: `Sorry, you can't change vacation mode for another {}hrs`".format(24-dayDifferenceNow(s.vacationMode[1])*24))
        else:
            s.vacationMode = (False, datetime.utcnow())
            await ctx.send(":white_check_mark: `Vacation Mode DISABLED`")
    else:
        await ctx.send(":x: `You need to start a streak first!`")

#
#
# ADMIN COMMANDS
#
#

@bot.command(hidden=True)
async def setmercies(ctx, user = None, mercies = None):
    if (not await isAdministrator(ctx)):
        return

    if (not isExpectedArgs( ((str, int), (str, int)), (user, mercies) )):
        msg = await ctx.send(":x: `!setmercies requires 2 arguments: <user> <mercies>`")
        await deleteInteraction((msg, ctx.message))
        return

    if (getStreaker(user)):
        getStreaker(user).mercies = int(mercies); backup()
    else:
        msg = await ctx.send(":x: `User '{}' not found`".format(user))
        await deleteInteraction((msg, ctx.message))
        return

    await ctx.send(":white_check_mark: `{0}'s mercies have been set to {1} {2}`".format(getStreaker(user).name, mercies, "DAYS" if int(mercies) > 1 else "DAY"))

@bot.command(hidden=True)
async def setstreak(ctx, user = None, newStreak = None, setToToday = None):
    if (not await isAdministrator(ctx)):
        return

    if (not isExpectedArgs( ((str, int), (str, int)), (user, newStreak) )):
        msg = await ctx.send(":x: `!setstreak requires 2 arguments: <user> <streak>`")
        await deleteInteraction((msg, ctx.message))
        return

    if (getStreaker(user)):
        s = getStreaker(user)
        if (not setToToday):
            s.lastPostTime = datetime.utcnow() - timedelta(1)
        elif (setToToday.isdigit()):
            s.lastPostTime = (datetime.utcnow() - timedelta(int(setToToday)))
        else:
            s.lastPostTime = datetime.utcnow()
        s.streak = int(newStreak)
        if (s.streak > s.streakRecord): s.streakRecord = s.streak
        backup()
    else:
        msg = await ctx.send(":x: `User '{}' not found`".format(user))
        await deleteInteraction((msg, ctx.message))
        return

    time_text = "DAYS"
    if (int(newStreak) == 1):
        time_text = "DAY"

    user = getStreaker(user)
    if (not setToToday):
        await ctx.send(":white_check_mark: `{0}'s streak has been set to {1} {2}. Their lastPostTime has been set to yesterday`".format(user.name, newStreak, time_text))
    else:
        if (not setToToday.isdigit()):
            await ctx.send(":white_check_mark: `{0}'s streak has been set to {1} {2}`".format(user.name, newStreak, time_text))
        else:
            await ctx.send(":white_check_mark: `{0}'s streak has been set to {1} {2}. Their lastPostTime has been set to {3} days ago`".format(user.name, newStreak, time_text, int(setToToday)))


@bot.command(hidden=True)
async def bumpstreak(ctx, user = None, setToToday = None):
    if (not await isAdministrator(ctx)):
        return

    if (not user):
        msg = await ctx.send(":x: `!bumpstreak requires 1 argument: <user>`")
        await deleteInteraction((msg, ctx.message))
        return

    if (getStreaker(user)):
        s = getStreaker(user)
        if (not setToToday):
            s.lastPostTime = datetime.utcnow() - timedelta(1)
        elif (setToToday.isdigit()):
            s.lastPostTime = (datetime.utcnow() - timedelta(int(setToToday)))
        else:
            s.lastPostTime = datetime.utcnow()
        s.streak = s.streak + 1
        if (s.streak > s.streakRecord): s.streakRecord = s.streak
        backup()
    else:
        msg = await ctx.send(":x: `User '{}' not found`".format(user))
        await deleteInteraction((msg, ctx.message))
        return

    time_text = "DAYS"
    if (s.streak == 1):
        time_text = "DAY"

    user = getStreaker(user)
    if (not setToToday):
        await ctx.send(":white_check_mark: `{0}'s streak has been bumped to {1} {2}. Their lastPostTime has been set to yesterday`".format(user.name, s.streak, time_text))
    else:
        if (not setToToday.isdigit()): setToToday = "0"
        await ctx.send(":white_check_mark: `{0}'s streak has been bumped to {1} {2}. Their lastPostTime has been set to {3} days ago`".format(user.name, s.streak, time_text, setToToday))

@bot.command(hidden=True)
async def checkday(ctx):
    if (not await isAdministrator(ctx)):
        return

    await processEndOfDay(ctx.message, True)

#
#
# CHECKER FUNCTIONS
#
#

def isExpectedArgs(types, args, decypherString = True):
    if type(args) == tuple: args = list(args)
    if (decypherString):
        # Go through each arg and try to decypher a value from it
        for x in range(0, len(args)):
            if (not args[x] or type(args[x]) != str): continue
            if args[x].isdigit(): args[x] = int(args[x]); continue
            # Why no .isbool()? >:(
            if args[x].lower() == "true": args[x] = True; continue
            if args[x].lower() == "false": args[x] = False; continue

    index=-1
    for kind in types:
        index+=1
        # If arg can be multiple types...
        if (type(kind) == tuple):
            # if arg is not any of the accepted types
            ## print("Checking if {0} arg is one of kinds {1}".format(args[index], ", ".join(map(str,kind))))
            if (not type(args[index]) in kind):
                return False
        # If arg can be only one type...
        else:
            # if arg is not its required type...
            ## print("Checking if {0} arg is kind {1}".format(args[index], kind))
            if (kind != type(args[index])):
                return False
    return True

async def isAdministrator(ctx):
    mod_role = discord.utils.get(ctx.message.guild.roles, id=462342299171684364)

    if (ctx.message.author.id != 359521958519504926 and mod_role not in ctx.message.author.roles):
        msg = await ctx.send(":x: `You do not have permission to do this`")
        time.sleep(3)

        await msg.delete()
        await ctx.message.delete()
        return False
    return True

#
#
# UTILITY FUNCTIONS
#
#

def getStreaker(user):
    if (not user):
        return False

    if (type(user) != int):
        # If we were not given an ID, assume it is a mention and pull it from the string
        if (not user[0].isdigit()):
            user = user.replace('<', '')
            user = user.replace('!', '')
            user = user.replace('@', '')
            user = user.replace('>', '')
        
        # If we still don't have an ID, assume it is a nickname and return false
        if (not user[0].isdigit()):
            return False

    for s in streakers:
        if s.id == int(user):
            return s
    return False

def getStreakGroups():
    lastHighestStreak = 0
    streakGroups = []

    streakers.sort(reverse=True, key=operator.attrgetter('streak'))

    for s in streakers:
        if s.streak != lastHighestStreak and s.streak != 0:
            lastHighestStreak = s.streak
            streakGroups.append(s.streak)

    return streakGroups          

async def deleteInteraction(msgs):
    time.sleep(3)
    if (type(msgs) == tuple):
        for msg in msgs:
            await msg.delete()
    else:
        await msgs.delete()

def dayDifferenceNow(oldTime, newTime=0):
    # if (newTime != 0): # FOR TESTING PURPOSES
    #     dayNow = newTime.day
    #     dayOld = oldTime.day

    #     dif = dayNow - dayOld

    #     if (dif > -1):
    #         return dif
    #     else:
    #         # if the month has rolled over, get the amount of days between the old time, the end of the month, and now
    #         mLength = monthrange(oldTime.year, oldTime.month)[1]
    #         dif = (mLength - dayOld) + dayNow
    #         return dif

    if (oldTime != None):
        dayNow = datetime.utcnow().day
        dayOld = oldTime.day

        dif = dayNow - dayOld

        if (dif > -1):
            return dif
        else:
            # if the month has rolled over, get the amount of days between the old time, the end of the month, and now
            mLength = monthrange(oldTime.year, oldTime.month)[1]
            dif = (mLength - dayOld) + dayNow
            return dif
    else:
        #print("old time is 0 :(")
        return 1

def getEmbedData():
    try:
        url = API["getURL"]
        data = requests.get(url).json()
    except Exception:
        print("\n*COULD NOT GET EMBED DATA. USING DEFAULTS...*\n")
        data = {
            "color": 0xD8410A,
            "footer": {
                "text": "Default",
                "icon_url": "https://cdn.discordapp.com/avatars/359521958519504926/dd83c78bd736e67c9801c077d99fb845.png"
            }
        }
    return data



# Backup all of the data
def backup():
    #if (DEBUG): return

    serializable_data = {}

    try: os.rename("data/dailies_data.json", "data/dailies_data_OLD.json")
    except Exception: pass

    with open("data/dailies_data.json", "w") as dailies_data_file:
        for s in streakers:
            id = str(s.id) # compliance with new Discord.py integer IDs
            serializable_data[id] = {}

            # Make compatible with v1.2 to v1.5 streak user class
            if (not hasattr(s, 'weekStreak')): s.weekStreak = 0
            if (not hasattr(s, 'streakRecord')): s.streakRecord = s.streak
            if (not hasattr(s, 'streakAllTime')): s.streakAllTime = s.streak
            if (not hasattr(s, 'mercies')): s.mercies = 0
            if (not hasattr(s, 'casual')): s.casual = False
            if (not hasattr(s, 'lowMercyWarn')): s.lowMercyWarn = True
            if (not hasattr(s, 'days')): s.days = {}
            if (not hasattr(s, 'vacationMode')): s.vacationMode = (False, datetime.utcnow() - timedelta(2))

            serializable_data[id]["name"] = s.name
            serializable_data[id]["streak"] = s.streak
            serializable_data[id]["weekStreak"] = s.weekStreak
            serializable_data[id]["streakRecord"] = s.streakRecord
            serializable_data[id]["streakAllTime"] = s.streakAllTime
            serializable_data[id]["mercies"] = s.mercies
            serializable_data[id]["lastPostTime"] = str(s.lastPostTime)
            serializable_data[id]["casual"] = s.casual
            serializable_data[id]["lowMercyWarn"] = s.lowMercyWarn
            serializable_data[id]["days"] = s.days
            serializable_data[id]["vacationMode"] = (s.vacationMode[0], str(s.vacationMode[1]))

        json.dump(serializable_data, dailies_data_file, indent=4, sort_keys=True)

# Load all of the backup data
def load_backup():
    #if (DEBUG): return
    json_data = {}

    try:
        with open("data/dailies_data.json", "r") as dailies_data_file:
            json_data = json.load(dailies_data_file)

            for id in json_data:
                #print("Loading id for {}".format(id))
                if (json_data[id]["lastPostTime"] != "None"):
                    time = datetime.strptime(json_data[id]["lastPostTime"], '%Y-%m-%d %H:%M:%S.%f')
                else:
                    time = None
                # Make compatible with v1.2 to v1.5 streak user class
                if (not "weekStreak" in json_data[id]): json_data[id]["weekStreak"] = 0
                if (not "streakRecord" in json_data[id]): json_data[id]["streakRecord"] = json_data[id]["streak"]
                if (not "streakAllTime" in json_data[id]): json_data[id]["streakAllTime"] = json_data[id]["streak"]
                if (not "mercies" in json_data[id]): json_data[id]["mercies"] = 0
                if (not "casual" in json_data[id]): json_data[id]["casual"] = False
                if (not "lowMercyWarn" in json_data[id]): json_data[id]["lowMercyWarn"] = True
                if (not "days" in json_data[id]): json_data[id]["days"] = {}
                if (not "vacationMode" in json_data[id]): json_data[id]["vacationMode"] = (False, datetime.utcnow() - timedelta(2))

                vacationModeTime = datetime.strptime(str(json_data[id]["vacationMode"][1]), '%Y-%m-%d %H:%M:%S.%f')

                streakers.append( Streaker( id=int(id),
                                            name=json_data[id].get("name"),
                                            days=json_data[id]["days"],
                                            lpt=time,
                                            streak=json_data[id]["streak"],
                                            streakRecord=json_data[id]["streakRecord"],
                                            streakAllTime=json_data[id]["streakAllTime"],
                                            weekStreak=json_data[id]["weekStreak"],
                                            mercies=json_data[id]["mercies"],
                                            casual=json_data[id]["casual"],
                                            lowMercyWarn = json_data[id]["lowMercyWarn"],
                                            vacationMode=(json_data[id]["vacationMode"][0], vacationModeTime)
                                            ))
    except Exception as e:
        print("\n**BACKUP MODIFIED OR CORRUPTED**\n")
        print(traceback.print_exc())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return
    raise error


if __name__ == "__main__":
    main()
    # If we don't have any arguments to process
    # if (len(sys.argv) == 1):
    #     main()
    # else: # Load up the test IDs
    #     with open("data/test_server.json", "r") as testServer:
    #         jsonData = json.load(testServer)

    #         DAILY_CHANNEL_ID = jsonData["DCID"]
    #         DDISC_CHANNEL_ID = jsonData["DDCID"]
    #         SPAM_CHANNEL_ID  = jsonData["SCID"]
    #         STREAKER_NOTIFY_ID = jsonData["SRID"]
    #     with open("data/token", "r") as token:
    #         BOT_ID = token.readline()
    #     main()
