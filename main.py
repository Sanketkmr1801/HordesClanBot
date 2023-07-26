import discord
from dotenv import load_dotenv
import os
import requests
import json
import time
from peewee import *
from server import keep_alive
import datetime

db = SqliteDatabase("clan.db")

class PlayerLog(Model):
    name = CharField()
    prestige = IntegerField()
    level = IntegerField()
    clan = CharField()
    gs = IntegerField()
    date_created = DateTimeField()

    class Meta:
        database = db  # This model uses the "clan.db" database.


db.connect()

db.create_tables([PlayerLog])

load_dotenv(dotenv_path="token.env")
token = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

def download_member_data(tag):
    clan_url = 'https://hordes.io/api/claninfo/info'
    headers = {
        'user-agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
    }
    payload = {"tag": tag}

    start_time = time.time()

    clan_data = requests.post(url=clan_url, headers=headers, data=json.dumps(payload))

    clan_data = clan_data.json()
    members = clan_data["members"]

    member_arr = []
    current_date = datetime.datetime.now()
    for member in members:
        # print(member["name"])
        name = member["name"]
        player_url = "https://hordes.io/api/playerinfo/search"
        headers = {
        'user-agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        }
        payload = {"name": name, "order": "fame", "limit": 100, "offset": 0, "tag": "-AE"}
        member_data = requests.post(url=player_url, headers=headers, data=json.dumps(payload))
        member_data = member_data.json()


        for member_s in member_data:
            if(member_s["name"] == name):
                member_arr.append(member_s)
                break
        
    end_time = time.time()
    duration = end_time - start_time
    print(member_arr, duration)
    rows = []
    for m  in member_arr:
        row = {}
        row["name"] = m["name"]
        row["prestige"] = m["prestige"]
        row["clan"] = m["clan"]
        row["gs"] = m["gs"]
        row["level"] = m["level"]
        row["date_created"] =  current_date
        rows.append(row)
        print(row)

    PlayerLog.insert_many(rows).execute()
    return member_arr

def get_latest_date(tag):
    latest_date = PlayerLog.select(PlayerLog.date_created).where(PlayerLog.clan == tag).order_by(PlayerLog.date_created.desc()).first()
    return latest_date

def get_next_reset_date(tag):
    latest_date = get_latest_date(tag)
    next_reset_date = None
    if latest_date:
        latest_date = latest_date.date_created

        print("latest date: " + date_to_string(latest_date))
        # Step 3: Calculate the next Wednesday's date
        days_until_wednesday = (2 - latest_date.weekday()) % 7
        next_wednesday_date = latest_date + datetime.timedelta(days=days_until_wednesday)

        # Step 4: Combine next Wednesday's date with midnight time to get the datetime
        next_reset_date = datetime.datetime.combine(next_wednesday_date, datetime.time.min)
        print("Next reset date : " + date_to_string(next_reset_date))

    else:
        print("No records found for tag '-AE' in the database.")

    return next_reset_date

def date_to_string(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

async def get_member_data(tag, message):
    print("working")
    current_date = datetime.datetime.now()
    latest_date = get_latest_date(tag)
    next_reset_date = get_next_reset_date(tag)
    print(next_reset_date, current_date)
    if((not next_reset_date) or current_date.date() > next_reset_date.date()):
        print("downloading new data for " + tag)
        await message.reply("downloading new data for " + tag + " on " + date_to_string(current_date))
        return download_member_data(tag)
    else:
        print("record found for " + tag)
        await message.reply("Record found for " + tag + " from " + date_to_string(latest_date.date_created))
        latest_date = latest_date.date_created
        query = PlayerLog.select().where((PlayerLog.clan == tag) & (PlayerLog.date_created == latest_date)).order_by(PlayerLog.prestige.desc())
        print(query)
        member_arr = query.execute()
        
        members = {}
        for m in member_arr:
            member = {}
            member["name"] = m.name
            member["prestige"] = m.prestige
            member["level"] = m.level
            member["clan"] = m.clan
            member["gs"] = m.gs
            member["date_created"] = m.date_created
            members[m.name] = member 
        
        return members
    
def table_to_obj(member_arr):
        members = {}
        for m in member_arr:
            member = {}
            member["name"] = m.name
            member["prestige"] = m.prestige
            member["level"] = m.level
            member["clan"] = m.clan
            member["gs"] = m.gs
            member["date_created"] = m.date_created
            members[m.name] = member 
        
        return members

def compare_members(tag, message = None):
    latest_date = get_latest_date(tag)
    if(latest_date):
        latest_date = latest_date.date_created
    second_latest_date = PlayerLog.select(PlayerLog.date_created).where((PlayerLog.clan == tag) & (PlayerLog.date_created < latest_date)).order_by(PlayerLog.date_created.desc()).first()

    if(second_latest_date):
        second_latest_date = second_latest_date.date_created

    print(latest_date, second_latest_date)
    latest_data = PlayerLog.select().where((PlayerLog.clan == tag) & (PlayerLog.date_created == latest_date)).execute()
    second_latest_data = PlayerLog.select().where((PlayerLog.clan == tag) & (PlayerLog.date_created == second_latest_date)).execute()

    latest_members = table_to_obj(latest_data)
    second_latest_members = table_to_obj(second_latest_data)

    diff_obj = {}
    for m in latest_members:
        latest_m = latest_members[m]
        latest_prestige = latest_m["prestige"]
        if(second_latest_members and (m in second_latest_members)):
            second_latest_m = second_latest_members[m]
        else: 
            second_latest_m = None
        if(second_latest_m):
            second_latest_prestige = second_latest_m["prestige"]
        else:
            second_latest_prestige = 0
        diff = latest_prestige - second_latest_prestige
        diff_obj[m] = {"p1" : latest_prestige, "p2" : second_latest_prestige, "diff" : diff}

    sorted_obj = sorted(diff_obj.items(), key = lambda x: x[1]["diff"], reverse = True)

    for m in sorted_obj:
        print(m)
    return sorted_obj

@client.event
async def on_ready():
  print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
  if message.author == client.user: return
  ae_officer_role = discord.utils.get(message.author.roles, name="Hordes Officer")
  if ae_officer_role is None:
      return

  if (message.content[0] == "!"):
    command = message.content.split(" ")[0]

    if (command.lower() == "!clanadd"):
        tag = message.content.split(" ")[1]
        if(tag):
            members = await get_member_data(tag, message)
            result_48 = "```Prestige above 48k\n"
            result_36 = "```Prestige above 36k\n"
            result_20 = "```Prestige above 20k\n"
            result_rest = "```Prestige above 0\n"
            
            for m in members:
                m = members[m]
                prestige = m["prestige"]
                name = m["name"]
                m_string = f"{name:<20} {prestige}\n"
                
                if(prestige > 48000):
                    result_48 += m_string
                elif(prestige > 36000):
                    result_36 += m_string
                elif(prestige > 20000):
                    result_20 += m_string       
                else:
                    result_rest += m_string

            result_48 += "```"
            result_36 += "```"
            result_20 += "```"
            result_rest += "```"
            await message.channel.send(result_48)
            await message.channel.send(result_36)
            await message.channel.send(result_20)
            await message.channel.send(result_rest)
    
    if (command.lower() == "!clandiff"):
        tag = message.content.split(" ")[1]
        if(tag):
            members = compare_members(tag)
            await message.channel.send("```Comparing this week and last week data for clan " + tag + "```")
            result_48 = f"```\nPrestige above 48k\n{'Name':<20} {'Week1':<8} {'Week2':<8} Diff\n"
            result_36 = f"```Prestige above 36k\n{'Name':<20} {'Week1':<8} {'Week2':<8} Diff\n"
            result_20 = f"```Prestige above 20k\n{'Name':<20} {'Week1':<8} {'Week2':<8} Diff\n"
            result_rest = f"```Prestige above 0\n{'Name':<20} {'Week1':<8} {'Week2':<8} Diff\n"
            
            for m, data in members:
                p1 = data["p1"]
                p2 = data["p2"]
                diff = data["diff"]
                name = m
                m_string = f"{name:<20} {p1:<8} {p2:<8} {diff}\n"
                
                if(p1 > 48000):
                    result_48 += m_string
                elif(p1 > 36000):
                    result_36 += m_string
                elif(p1 > 20000):
                    result_20 += m_string       
                else:
                    result_rest += m_string

            result_48 += "```"
            result_36 += "```"
            result_20 += "```"
            result_rest += "```"
            await message.channel.send(result_48)
            await message.channel.send(result_36)
            await message.channel.send(result_20)
            await message.channel.send(result_rest)

client.run(token=token)