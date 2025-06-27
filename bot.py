import discord
from discord.ext import commands, tasks
from discord.ui import *
import asyncio
import json
import os
import random
import time
import datetime
import uuid
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import razorpay  

leaderboard_path = "weekly_lb.json"
monthly_leaderboard_path = "monthly_lb.json"

with open("config.json", "r") as config_file:
    config = json.load(config_file)
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
RAZORPAY_KEY_ID = config["razorpay_key_id"]
RAZORPAY_KEY_SECRET = config["razorpay_secret"]
SERVICE_ACCOUNT_FILE = config["google_service_account_file"]
SCOPES = config["google_sheets_scopes"]


bot = commands.Bot(intents=discord.Intents.all(), command_prefix='s!')
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def load_json(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                return json.load(file)
        return {}
    except json.JSONDecodeError:
        return {}

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Bot is ready. Logged in as {bot.user.name}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Tournaments in Swadeshi LAN"))

def load_leaderboard(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as lb_file:
            return json.load(lb_file)
    return {}

def save_leaderboard(file_path, data):
    with open(file_path, "w") as lb_file:
        json.dump(data, lb_file, indent=4)
    
def generate_tournament_id():
    tournament_id = random.randint(100000, 999999)
    try:
        with open("tournaments.json", "r") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        data = {} 
    while tournament_id in data:
        tournament_id = random.randint(100000, 999999)
    return tournament_id

def create_google_sheet(tournament_name):
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    
    # Create the Google Sheet
    sheet_body = {'properties': {'title': f"{tournament_name} Registrations"}}
    spreadsheet = service.spreadsheets().create(body=sheet_body).execute()
    spreadsheet_id = spreadsheet['spreadsheetId']

    # Give access to your Google account
    drive_service = build('drive', 'v3', credentials=creds)
    permission_body = {
        'type': 'user',  
        'role': 'writer',  
        'emailAddress': "swadeshilan@gmail.com"  
    }
    drive_service.permissions().create(
        fileId=spreadsheet_id,
        body=permission_body,
        sendNotificationEmail=False
    ).execute()

    return spreadsheet_id

def save_tournament_data(tournament_id, data):
    file_path = "tournaments.json"
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            all_data = json.load(file)
    else:
        all_data = {}
    all_data[tournament_id] = data
    with open(file_path, "w") as file:
        json.dump(all_data, file, indent=4)

def generate_receipt(team, players, contact, amount, receipt_id, match_datetime, tournament_name):
    os.makedirs("receipts", exist_ok=True)
    qr_path = f"receipts/{receipt_id}_qr.png"
    logo_path = "logo.png"
    pdf_path = f"receipts/{receipt_id}_receipt.pdf"

    qr = qrcode.make(receipt_id).resize((100, 100))
    qr.save(qr_path)

    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name="Title", fontSize=16, leading=20, alignment=1, textColor=colors.HexColor("#1F4E79"))
    section_heading = ParagraphStyle(name="Heading", fontSize=13, leading=15, textColor=colors.HexColor("#004080"), spaceBefore=12, spaceAfter=6)
    normal = styles["Normal"]
    small_gray = ParagraphStyle(name="SmallGray", fontSize=8, textColor=colors.grey)

    # Header Row
    header_table = Table([[
        RLImage(logo_path, width=30*mm, height=30*mm),
        Paragraph(f"<b>{tournament_name} Invoice</b><br/><i>Organized by Swadeshi LAN</i>", title_style),
        RLImage(qr_path, width=30*mm, height=30*mm)
    ]], colWidths=[60, 360, 60])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    player_names = ", ".join(players)
    receipt_table_data = [
        ['Receipt ID', receipt_id],
        ['Team Name', team],
        ['Players', player_names],
        ['Contact Number', contact],
        ['Amount Paid', f"{amount} INR"],
        ['Match Date & Time', match_datetime],
    ]
    receipt_table = Table(receipt_table_data, colWidths=[150, 360])
    receipt_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    elements.append(receipt_table)

    elements.append(Paragraph("Important Notes", section_heading))
    elements.append(Paragraph("""
        <ul>
        <li>Arrive 30 minutes before match time.</li>
        <li>Bring this recipt if this is a LAN tournament.</li>
        <li>Contact team Swadeshi LAN at discord if needed.</li>
        </ul>
    """, normal))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Thank you for registering. Good luck!", normal))
    elements.append(Paragraph("Support: discord.gg/SwadeshiLAN | Email: contact@swadeshilan.in", small_gray))

    doc.build(elements)
    return pdf_path

class ConfirmationView(discord.ui.View):
    def __init__(self,tournament_name, entry_fee, spreadsheet_id, category, tournament_id, msg, max_teams, channel, user_id,name,age,team_name,team_details,contact_number):
        super().__init__()
        self.tournament_name = tournament_name
        self.entry_fee = entry_fee
        self.spreadsheet_id = spreadsheet_id
        self.tournament_id = tournament_id
        self.channel = channel
        self.msg=msg
        self.name = name
        self.age = age
        self.team_name= team_name
        self.team_details=team_details
        self.contact_number=contact_number
        self.max_teams=max_teams
        self.user_id =user_id
        self.category = category

    @discord.ui.button(label="Confirm Registration", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        print(f"Interaction User ID: {interaction.user.id}, Stored User ID: {self.user_id}")
        if interaction.user.id != int(self.user_id):
            return await interaction.response.send_message("You cannot confirm someone else's registration!", ephemeral=True)
        user_channel = self.channel
        async for message in user_channel.history(limit=10): 
            if message.author == interaction.guild.me:
                if f"{interaction.user.id}" in message.content:
                    await message.edit(view=None)
                    break
            
        embbed = discord.Embed(description=f"{interaction.user.name} responded with **'Confirm Registration'**")
        await interaction.response.send_message(embed=embbed)
        user_id = self.user_id
        secret_id = uuid.uuid4().hex
        user = interaction.user
        razorpay_client.set_app_details({"title" : "Swadeshi LAN Payments", "version" : "1.0"})
        payment_order = razorpay_client.payment_link.create({
            "amount": self.entry_fee * 100, 
            "currency": "INR",
            "description": f"Registration Fee of {self.tournament_name}",
            "callback_url": "https://discord.gg/DqaV6487yG",
            "expire_by": int(time.time()) + 1200,
            
        })
       
        
        payment_link = payment_order['short_url']
        
        
        invoice_embed = discord.Embed(title='**Payment Invoice**',
                                      colour=0xffffff,
                      timestamp=datetime.datetime.now())
        invoice_embed.add_field(name='**Pay here:**', value=f'[Click Here]({payment_link})', inline=True)
        invoice_embed.add_field(name='**Amount**', value=f'₹`{self.entry_fee}`', inline=True)
        invoice_embed.set_author(name="Swadeshi LAN",
                icon_url=interaction.guild.icon.url)
        invoice_embed.set_footer(text="Made by Scott with ❤")
        invoice_msg = await user_channel.send(embed=invoice_embed)
        waiting_embed = discord.Embed()
        waiting_embed.set_footer(text='Waiting for transaction...', icon_url='https://cdn.discordapp.com/emojis/1243968358907514922.gif?size=44&quality=lossless')
        waiting_msg = await user_channel.send(embed=waiting_embed)
        start_time = time.time()
        timeout_minutes = 20
        while time.time() - start_time < timeout_minutes * 60:
            await asyncio.sleep(5)
            
            payment_status = razorpay_client.payment_link.fetch(payment_order['id'])
                                                
            if payment_status.get("status") == "paid":
 
                waiting_embed = discord.Embed()
                waiting_embed.set_footer(text='Payment Recived Succefully', icon_url='https://cdn.discordapp.com/emojis/1221945764545167422.webp?size=28&animated=true')
                await waiting_msg.edit(content=user.mention,embed=waiting_embed)
                await user_channel.edit(name=f"{interaction.user.name}-paid")
                file_path = "tournaments.json"
                if os.path.exists(file_path):
                    with open(file_path, "r") as file:
                        all_data = json.load(file)
                else:
                    all_data = {}
                row_number=0
                for tournament_id, tournament_data in all_data.items():
                    if tournament_data["spreadsheet_id"] == self.spreadsheet_id:
                        row_number = tournament_data["registerd_teams"] + 2
                file_path = "tournaments.json"
                if os.path.exists(file_path):
                    with open(file_path, "r") as file:
                        all_data = json.load(file)
                else:
                    all_data = {}
                role = discord.utils.get(interaction.guild.roles, name=f"{self.tournament_id}-registerd")
                approval_view = ApprovalButtons(user, self.spreadsheet_id, row_number, role,self.channel,secret_id)
                embbed = discord.Embed(title="**Mod Approval**",description=f"{user.mention} a moderator will check and approve your applcation before final Registration. Please wait.")
                await user_channel.send(content="<@&1238841033341665281>", embed=embbed,view=approval_view)

                for tournament_id, tournament_data in all_data.items():
                    if tournament_data["spreadsheet_id"] == self.spreadsheet_id:
                        
                        tournament_data["teams"][secret_id] ={
                            "team_name": self.team_name.value,
                            "players": self.team_details.value.split(","),
                            "contact_number": self.contact_number.value,
                            "registration" : "Paid",
                            "verified": False,
                            "otp": None,
                            "otp_expiry": None,                     
                            "team_id": interaction.user.id
                        }
                        break

                with open(file_path, "w") as file:
                    json.dump(all_data, file, indent=4)
                break

    @discord.ui.button(label="Edit Details", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != int(self.user_id):

            return await interaction.response.send_message("You cannot edit someone else's details!", ephemeral=True)
        await interaction.response.send_modal(EditRegistrationModal(self.tournament_name, self.entry_fee, self.spreadsheet_id, self.category, self.tournament_id, self.msg, self.max_teams,channel=self.channel, user_id=self.user_id))
class CloseRegistration(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        disabled_button = Button(label="Registrations Closed", disabled=True, style=discord.ButtonStyle.red)
        self.add_item(disabled_button)

class ApprovalButtons(discord.ui.View):
    def __init__(self, user, spreadsheet_id, row_number, role,channel, secret_id):
        super().__init__(timeout=None)
        self.user = user
        self.channel = channel
        self.spreadsheet_id = spreadsheet_id
        self.row_number = row_number
        self.secret_id = secret_id
        self.role = role

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Only moderators can use this command!", ephemeral=True)
            return
        embed = discord.Embed(description=f"{interaction.user.name} responded with **'Approve'**")
        await interaction.response.send_message(embed=embed)
        await self.update_spreadsheet("Approved")
        await self.user.add_roles(self.role)
        file_path = "tournaments.json"
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                all_data = json.load(file)
        else:
            all_data = {}
        tournament_name =  None
        info_channel = None
        timestamp = 0
        for tournament_id, tournament_data in all_data.items():
            if tournament_data["spreadsheet_id"] == self.spreadsheet_id:
                tournament_data["registerd_teams"] += 1
                tournament_name = tournament_data["tournament_name"]
                info_channel = tournament_data["info_channel_id"]
                amount = tournament_data["entry_fee"]
                timestamp = tournament_data["tournament_time"]
                for secret_id, team in tournament_data["teams"].items():
                    if team["team_id"] == self.user.id:  
                        team["registration"] = "Approved"
                        name=team["team_name"]  
                        players=team["players"]
                        contact=team["contact_number"]
                        receipt_id=secret_id
                        
                        break
        with open(file_path, "w") as file:
            json.dump(all_data, file, indent=4) 
        dt = datetime.datetime.fromtimestamp(timestamp)
        match_datetime = dt.strftime("%d-%m-%Y %I:%M %p")    
        
        path = generate_receipt(name, players, contact, amount, receipt_id, match_datetime, tournament_name)    
        picture = discord.File(path, filename="receipt.pdf")
        picture1 = discord.File(path, filename="receipt.pdf")
        embed = discord.Embed(title="**Approved**",description=f"{interaction.user.mention} have approved your Application. Now you are registerd For **{tournament_name}** check <#{info_channel}> for All updates \n **Good Luck For Tournament**\n**⚠ YOUR TEAM ID IS YOUR ``{secret_id}``**",color=0x04f500)  
        embed.add_field(name="Tournament Time",value=f"**<t:{timestamp}:F>**")
        await self.user.send(embed=embed,file=picture)
        await interaction.followup.send(content=self.user.mention,embed=embed,file=picture1)    
        await self.channel.edit(name=f"{self.user.name}-approved")
        self.stop()


    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Only moderators can use this command!", ephemeral=True)
            return
        embed = discord.Embed(description=f"{interaction.user.name} responded with **'Reject'**")
        await interaction.response.send_message(embed=embed)
        await self.update_spreadsheet("Rejected")
        file_path = "tournaments.json"
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                all_data = json.load(file)
        else:
            all_data = {}
        for tournament_id, tournament_data in all_data.items():
            if tournament_data["spreadsheet_id"] == self.spreadsheet_id:
                for secret_id, team in tournament_data["teams"].items():
                    if team["team_id"] == self.user.id:  
                        team["registration"] = "Rejected"  
                        break
        with open(file_path, "w") as file:
            json.dump(all_data, file, indent=4)
        embed = discord.Embed(title="**Rejected**",description=f"{interaction.user.mention} have rejected your Application. Please Contact Staff For More information\n**⚠ YOUR TEAM NUMBER IS YOUR LEADERS'S DISCORD ID**",color=15548997)  
        await interaction.followup.send(content=self.user.mention,embed=embed) 
        await self.channel.edit(name=f"{self.user.mention}-rejected")
        self.stop()

    async def update_spreadsheet(self, status):
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        range_ = f"Sheet1!G{self.row_number}" 
        values = [[status]]
        service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_,
            valueInputOption="RAW",
            body={"values": values}
        ).execute()


class RegistrationModal(discord.ui.Modal):
    def __init__(self, tournament_name, entry_fee, spreadsheet_id, category, tournament_id, msg, max_teams):
        super().__init__(title=f"Register for Tournament")
        self.tournament_name = tournament_name
        self.entry_fee = entry_fee
        self.spreadsheet_id = spreadsheet_id
        self.tournament_id = tournament_id
        self.msg=msg
        self.max_teams=max_teams
        self.category = category

        self.name = discord.ui.TextInput(label="Name", placeholder="Enter your full name")
        self.age = discord.ui.TextInput(label="Age", placeholder="Enter your age")
        self.team_name = discord.ui.TextInput(label="Team Name", placeholder="Enter your Team Name")
        self.team_details = discord.ui.TextInput(label="Team Members in-game names", placeholder="Enter your Team Member's in-game names (seperated by commas)")
        self.contact_number = discord.ui.TextInput(label="Contact Number", placeholder="Enter your Contact Number")

        self.add_item(self.name)
        self.add_item(self.age)
        self.add_item(self.team_name)
        self.add_item(self.team_details)
        self.add_item(self.contact_number)

    async def on_submit(self, interaction: discord.Interaction):
        file_path = "tournaments.json"
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                 all_data = json.load(file)
        else:
            all_data = {}
        registred_teams=0
        for tournament_id, tournament_data in all_data.items():
            if tournament_data["spreadsheet_id"] == self.spreadsheet_id:
                registred_teams = tournament_data["registerd_teams"]
        if registred_teams == self.max_teams - 1:
            for tournament_id, tournament_data in all_data.items():
                if tournament_data["spreadsheet_id"] == self.spreadsheet_id:
                    tournament_data["Registartion Closed"]
            await self.msg.edit(view=CloseRegistration())

        user_id = str(interaction.user.id)
        user = interaction.user
        user_channel = await self.category.create_text_channel(
            f"{interaction.user.name}-registration",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True)
            }
        )
        await interaction.response.send_message(f"Complete Your Registration in <#{user_channel.id}>", ephemeral=True)
        embed = discord.Embed(title="Your Registration Details",
                        description=f"```Name: {self.name.value}\nAge: {self.age.value}\nTeam: {self.team_name.value}\nMembers: {self.team_details.value}\nContact: {self.contact_number.value}```",
                        colour=0xffffff, timestamp=datetime.datetime.now())
        embed.set_author(name="Swadeshi LAN",
            icon_url=interaction.guild.icon.url)
        embed.set_thumbnail(url=f"{interaction.guild.icon.url}")
        embed.set_footer(text="Made by Scott with ❤")
        await user_channel.send(content=f"<@{user_id}>", embed=embed, view=ConfirmationView(self.tournament_name, self.entry_fee, self.spreadsheet_id, self.category, self.tournament_id, self.msg, self.max_teams,user_channel,int(user_id), self.name, self.age, self.team_name, self.team_details, self.contact_number))

class EditRegistrationModal(discord.ui.Modal):
    def __init__(self, tournament_name, entry_fee, spreadsheet_id, category, tournament_id, msg, max_teams,channel ,user_id):
        super().__init__(title=f"Edit Your Details")
        self.tournament_name = tournament_name
        self.entry_fee = entry_fee
        self.spreadsheet_id = spreadsheet_id
        self.tournament_id = tournament_id
        self.channel = channel
        self.msg=msg
        self.user_id = user_id
        self.max_teams=max_teams
        self.category = category

        self.name = discord.ui.TextInput(label="Name", placeholder="Enter your full name")
        self.age = discord.ui.TextInput(label="Age", placeholder="Enter your age")
        self.team_name = discord.ui.TextInput(label="Team Name", placeholder="Enter your Team Name")
        self.team_details = discord.ui.TextInput(label="Team Members in-game names", placeholder="Enter your Team Member's in-game names")
        self.contact_number = discord.ui.TextInput(label="Contact Number", placeholder="Enter your Contact Number")

        self.add_item(self.name)
        self.add_item(self.age)
        self.add_item(self.team_name)
        self.add_item(self.team_details)
        self.add_item(self.contact_number)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id
        user = interaction.user
        user_channel = self.channel
        async for message in user_channel.history(limit=10): 
            if message.author == interaction.guild.me:  
                embed = discord.Embed(title="Your Registration Details",
                                description=f"```Name: {self.name.value}\nAge: {self.age.value}\nTeam: {self.team_name.value}\nMembers: {self.team_details.value}\nContact: {self.contact_number.value}```",
                                colour=0xffffff, timestamp=datetime.datetime.now())
                embed.set_author(name="Swadeshi LAN",
                    icon_url=interaction.guild.icon.url)
                embed.set_thumbnail(url=f"{interaction.guild.icon.url}")
                embed.set_footer(text="Made by Scott with ❤")
                embbed = discord.Embed(description=f"{interaction.user.name} responded with **'Edit Details'**")
                await interaction.response.send_message(embed=embbed)
                await message.edit(content=f"<@{user_id}>", embed=embed, view=ConfirmationView(self.tournament_name, self.entry_fee, self.spreadsheet_id, self.category, self.tournament_id, self.msg, self.max_teams,user_channel,int(user_id), self.name, self.age, self.team_name,self.team_details,self.contact_number))
        

class RegisterButton(discord.ui.View):
    def __init__(self, spreadsheet_id, category, tournament_name, entry_fee, tournament_id,msg,max_teams):
        super().__init__(timeout=None)
        self.spreadsheet_id = spreadsheet_id
        self.category = category
        self.tournament_name = tournament_name
        self.entry_fee = entry_fee
        self.msg=msg
        self.max_teams=max_teams
        self.tournament_id = tournament_id
        self.setup_buttons()

    def setup_buttons(self):
        button = discord.ui.Button(label='Register Now', custom_id='join', style=discord.ButtonStyle.green)
        button.callback = self.register
        self.add_item(button)

    async def register(self, interaction: discord.Interaction):
        modal = RegistrationModal(self.tournament_name, self.entry_fee, self.spreadsheet_id, self.category, self.tournament_id, self.msg, self.max_teams)
        await interaction.response.send_modal(modal)


@bot.tree.command(name="about_us", description="Shows About Swadeshi LAN")
async def about_us(interaction: discord.Interaction):
    embed = discord.Embed(title="ABOUT SWADESHI LAN",
                      description="𝙒𝙚 𝙖𝙧𝙚 𝙜𝙖𝙢𝙚𝙧𝙨 𝙟𝙪𝙨𝙩 𝙡𝙞𝙠𝙚 𝙮𝙤𝙪.\n\n➝𝙊𝙪𝙧 𝙖𝙞𝙢 𝙞𝙨 𝙩𝙤 𝙘𝙝𝙖𝙣𝙜𝙚 𝙩𝙝𝙚 𝙥𝙚𝙧𝙨𝙥𝙚𝙘𝙩𝙞𝙫𝙚 𝙤𝙛 𝙀-𝙨𝙥𝙤𝙧𝙩𝙨 𝙞𝙣 𝙄𝙣𝙙𝙞𝙖. 𝙃𝙪𝙣𝙙𝙧𝙚𝙙𝙨 𝙤𝙛 𝙩𝙤𝙪𝙧𝙣𝙖𝙢𝙚𝙣𝙩𝙨 𝙩𝙖𝙠𝙚 𝙥𝙡𝙖𝙘𝙚 𝙚𝙖𝙘𝙝 𝙙𝙖𝙮 𝙞𝙣 𝙫𝙖𝙧𝙞𝙤𝙪𝙨 𝙥𝙡𝙖𝙘𝙚𝙨 𝙗𝙪𝙩 𝙬𝙝𝙖𝙩 𝙖𝙗𝙤𝙪𝙩 𝙪𝙨? 𝙏𝙝𝙚𝙧𝙚 𝙖𝙧𝙚 𝙨𝙚𝙫𝙚𝙧𝙖𝙡 𝙜𝙖𝙢𝙚𝙧𝙨 𝙤𝙣 𝙞𝙣𝙩𝙚𝙧𝙣𝙚𝙩 𝙞𝙣 𝙄𝙣𝙙𝙞𝙖 𝙗𝙪𝙩 𝙬𝙝𝙚𝙧𝙚'𝙨 𝙩𝙝𝙚 𝙀-𝙨𝙥𝙤𝙧𝙩𝙨 𝙘𝙤𝙢𝙢𝙪𝙣𝙞𝙩𝙮 𝙬𝙝𝙤 𝙖𝙘𝙩𝙪𝙖𝙡𝙡𝙮 𝙨𝙪𝙥𝙥𝙤𝙧𝙩 𝙦𝙪𝙖𝙡𝙞𝙩𝙮 𝙜𝙖𝙢𝙞𝙣𝙜 𝙚𝙭𝙥𝙚𝙧𝙞𝙚𝙣𝙘𝙚 𝙖𝙣𝙙 𝙥𝙧𝙤𝙫𝙞𝙙𝙚 𝙜𝙧𝙚𝙖𝙩 𝙛𝙚𝙖𝙩𝙪𝙧𝙚𝙨.\n\n➝𝙒𝙚 𝙖𝙧𝙚 𝙝𝙚𝙧𝙚 𝙩𝙤 𝙧𝙚𝙫𝙤𝙡𝙪𝙩𝙞𝙤𝙣𝙞𝙯𝙚 𝙀-𝙨𝙥𝙤𝙧𝙩𝙨 𝙘𝙤𝙢𝙢𝙪𝙣𝙞𝙩𝙮 𝙩𝙤 𝙢𝙖𝙠𝙚 𝙞𝙩 𝙗𝙚𝙩𝙩𝙚𝙧 𝙥𝙡𝙖𝙘𝙚 𝙛𝙤𝙧 𝙚𝙫𝙚𝙧𝙮𝙤𝙣𝙚.\n\n➝𝙒𝙚 𝙥𝙧𝙤𝙫𝙞𝙙𝙚 𝙜𝙤𝙤𝙙 𝙦𝙪𝙖𝙡𝙞𝙩𝙮 𝙩𝙤𝙪𝙧𝙣𝙖𝙢𝙚𝙣𝙩𝙨 𝙤𝙛 𝙋𝘾 𝙜𝙖𝙢𝙚𝙨 𝙩𝙤 𝙚𝙫𝙚𝙧𝙮𝙤𝙣𝙚 𝙬𝙝𝙤 𝙬𝙖𝙣𝙩 𝙩𝙤 𝙖𝙘𝙝𝙞𝙚𝙫𝙚 𝙞𝙣 𝙩𝙝𝙞𝙨 𝙛𝙞𝙚𝙡𝙙. 𝙐𝙨 𝙬𝙞𝙩𝙝 𝙮𝙤𝙪𝙧 𝙨𝙪𝙥𝙥𝙤𝙧𝙩 𝙘𝙖𝙣 𝙙𝙤 𝙖𝙣𝙮𝙩𝙝𝙞𝙣𝙜 𝙞𝙣 𝙩𝙝𝙞𝙨 𝙜𝙚𝙣𝙚𝙧𝙖𝙩𝙞𝙤𝙣.\n\n➝𝙒𝙚 𝙬𝙞𝙡𝙡 𝙘𝙤𝙣𝙙𝙪𝙘𝙩 𝙨𝙚𝙫𝙚𝙧𝙖𝙡 𝙩𝙤𝙪𝙧𝙣𝙖𝙢𝙚𝙣𝙩𝙨 𝙤𝙛 𝙥𝙤𝙥𝙪𝙡𝙖𝙧 𝙁𝙋𝙎 𝘾𝙤𝙢𝙥𝙚𝙩𝙞𝙩𝙞𝙫𝙚 𝙂𝙖𝙢𝙚𝙨 𝙡𝙞𝙠𝙚 𝙑𝙖𝙡𝙤𝙧𝙖𝙣𝙩, 𝘾𝙎𝙂𝙊. 𝙊𝙫𝙚𝙧𝙬𝙖𝙩𝙘𝙝2 𝙚𝙩𝙘.\n\n𝙏𝙝𝙖𝙩'𝙨 𝙬𝙝𝙮 𝙬𝙚 𝙣𝙚𝙚𝙙 𝙮𝙤𝙪𝙧 𝙨𝙪𝙥𝙥𝙤𝙧𝙩 𝙩𝙤 𝙢𝙖𝙠𝙚 𝙩𝙝𝙞𝙨 𝙝𝙖𝙥𝙥𝙚𝙣 𝙖𝙡𝙡 𝙖𝙧𝙤𝙪𝙣𝙙 𝙤𝙪𝙧 𝙣𝙖𝙩𝙞𝙤𝙣, 𝙗𝙚𝙘𝙖𝙪𝙨𝙚 𝙩𝙤𝙜𝙚𝙩𝙝𝙚𝙧 𝙬𝙚 𝙘𝙖𝙣 𝙘𝙤𝙣𝙦𝙪𝙚𝙧 𝙩𝙝𝙚 𝙬𝙤𝙧𝙡𝙙.",
                      colour=0xffffff,
                      timestamp=datetime.datetime.now())
    embed.set_author(name="Swadeshi LAN",
                 icon_url="https://images-ext-1.discordapp.net/external/QOk3dZiqvebSPhvtzY1xSDWvOlBRWAlFon7bFhBzqTs/%3Fsize%3D1024/https/cdn.discordapp.com/icons/1238836855839916122/9c1a8e1a1d2ea4714564419970a6d4b9.png?format=webp&quality=lossless")
    embed.set_thumbnail(url=f"{interaction.guild.icon.url}")
    embed.set_image(url="https://media.discordapp.net/attachments/995322883008118865/1346780012732223550/swadeshi_lan_hand_tag.gif?ex=67c96e20&is=67c81ca0&hm=b633a798c557a2fb14cf9d0b6da2ecdc39e96f81676e2f2e9a3181964ac682df&=")
    embed.set_footer(text="Made by Scott with ❤")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="rules", description="Shows Rules of Swadeshi LAN")
async def rules(interaction: discord.Interaction):
    embed = discord.Embed(title="RULES",
                      description="~> 𝙉𝙤 𝙛𝙞𝙜𝙝𝙩𝙞𝙣𝙜. 𝙍𝙚𝙨𝙥𝙚𝙘𝙩 𝙚𝙫𝙚𝙧𝙮𝙤𝙣𝙚 𝙚𝙦𝙪𝙖𝙡𝙡𝙮.\n~> 𝙂𝙞𝙫𝙚𝙣 𝙏𝙖𝙜 𝙖𝙣𝙙 𝙏𝙚𝙖𝙢 𝙣𝙖𝙢𝙚 𝙙𝙞𝙨𝙩𝙧𝙞𝙗𝙪𝙩𝙚𝙙 𝙗𝙮 𝙪𝙨 𝙘𝙖𝙣𝙩 𝙗𝙚 𝙘𝙝𝙖𝙣𝙜𝙚 𝙖𝙣𝙙 𝙧𝙚𝙨𝙥𝙚𝙘𝙩 𝙞𝙩.\n~> 𝙍𝙚𝙨𝙥𝙚𝙘𝙩𝙞𝙣𝙜 𝙮𝙤𝙪𝙧 𝙘𝙤𝙖𝙘𝙝 𝙙𝙚𝙘𝙞𝙨𝙞𝙤𝙣𝙨 𝙖𝙣𝙙 𝙩𝙝𝙚𝙞𝙧 𝙤𝙥𝙞𝙣𝙞𝙤𝙣.\n~> 𝙍𝙚𝙨𝙥𝙚𝙘𝙩𝙞𝙣𝙜 𝙮𝙤𝙪𝙧 𝙩𝙚𝙖𝙢 𝙖𝙣𝙙 𝙡𝙞𝙨𝙩𝙚𝙣𝙞𝙣𝙜 𝙩𝙤 𝙩𝙝𝙚𝙢.\n~> 𝘽𝙧𝙚𝙖𝙠𝙞𝙣𝙜 𝙮𝙤𝙪𝙧 𝙚𝙦𝙪𝙞𝙥𝙢𝙚𝙣𝙩 𝙬𝙞𝙡𝙡 𝙧𝙚𝙨𝙪𝙡𝙩 𝙞𝙣 𝙥𝙚𝙣𝙖𝙡𝙩𝙮 𝙖𝙣𝙙 𝙖 𝙝𝙚𝙖𝙫𝙮 𝙛𝙞𝙣𝙚. 𝙄𝙛 𝙩𝙝𝙚 𝙙𝙖𝙢𝙖𝙜𝙚 𝙞𝙨 𝙢𝙤𝙧𝙚 𝙩𝙝𝙖𝙣 𝙚𝙭𝙥𝙚𝙘𝙩𝙚𝙙 𝙩𝙝𝙚𝙣 𝙮𝙤𝙪 𝙬𝙞𝙡𝙡 𝙗𝙚 𝙙𝙞𝙨𝙦𝙪𝙖𝙡𝙞𝙛𝙞𝙚𝙙.\n~> 𝙉𝙤 𝙙𝙞𝙨𝙘𝙧𝙞𝙢𝙞𝙣𝙖𝙩𝙞𝙤𝙣 𝙨𝙝𝙤𝙪𝙡𝙙 𝙗𝙚 𝙙𝙤𝙣𝙚 𝙗𝙖𝙨𝙚𝙙 𝙤𝙣 𝙖𝙜𝙚, 𝙧𝙚𝙡𝙞𝙜𝙞𝙤𝙣, 𝙘𝙤𝙡𝙤𝙪𝙧, 𝙘𝙖𝙨𝙩𝙚.\n~> 𝙉𝙤 𝙉𝙎𝙁𝙒 𝙘𝙤𝙣𝙩𝙚𝙣𝙩, 𝙉𝙤 𝙜𝙤𝙧𝙚, 𝙉𝙤 𝙙𝙞𝙨𝙩𝙪𝙧𝙗𝙞𝙣𝙜 𝙞𝙢𝙖𝙜𝙚𝙨, 𝙚𝙩𝙘. 𝙨𝙝𝙤𝙪𝙡𝙙 𝙗𝙚 𝙥𝙤𝙨𝙩𝙚𝙙 𝙝𝙚𝙧𝙚.\n~> 𝘽𝙚 𝙧𝙚𝙨𝙥𝙚𝙘𝙩𝙛𝙪𝙡 𝙬𝙞𝙩𝙝 𝙢𝙤𝙙𝙚𝙧𝙖𝙩𝙤𝙧𝙨 𝙖𝙣𝙙 𝙛𝙚𝙡𝙡𝙤𝙬 𝙜𝙖𝙢𝙚𝙧𝙨.\n𝙃𝙤𝙥𝙚 𝙮𝙤𝙪 𝙝𝙖𝙫𝙚 𝙖 𝙛𝙪𝙣 𝙩𝙞𝙢𝙚 𝙜𝙖𝙢𝙞𝙣𝙜 𝙬𝙞𝙩𝙝 𝙐𝙎!",
                      colour=0xffffff,
                      timestamp=datetime.datetime.now())
    embed.set_author(name="Swadeshi LAN",
                 icon_url=interaction.guild.icon.url)
    embed.set_thumbnail(url=f"{interaction.guild.icon.url}")
    embed.set_image(url="https://media.discordapp.net/attachments/995322883008118865/1346777318080778270/swadeshi_lan_hand_tag.gif?ex=67c96b9e&is=67c81a1e&hm=660eaeee5881b011ea7e7ba01afb7e1c0064c43e50587b21fb64b275cc488573&=")
    embed.set_footer(text="Made by Scott with ❤")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="create_tournament", description="Creates a Tournament")
async def create_tournament(interaction: discord.Interaction, tournament_name: str, entry_fee: int, details: str, max_teams: int, image: discord.Attachment, date_time: str):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ Only moderators can use this command!", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    tournament_id=generate_tournament_id()
    category = await interaction.guild.create_category(tournament_name)
    spreadsheet_id = create_google_sheet(tournament_name)
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    values = [["Team Leader Name", "Team Leader Age", "Team Leader's Discord ID", "Team Leader's Discord Name", "Team Name", "Team Members Details", "Contact Number", "Payment","Secret ID"]]
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()
    role = await interaction.guild.create_role(name=f"{tournament_id}-registerd")
    date_time = date_time.strip()
    target_time = datetime.datetime.strptime(date_time, "%d-%m-%Y %H:%M")
    timestamp = int(target_time.timestamp())
    info_channel = await interaction.guild.create_text_channel(
            f"{tournament_name}-updates",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
            },
            category=category
        )
    embed = discord.Embed(title=tournament_name,colour=0xffffff,
                      description=f"> {details}",
                      timestamp=datetime.datetime.now())
    embed.set_author(name="Swadeshi LAN",
                icon_url=interaction.guild.icon.url)
    embed.set_thumbnail(url=f"{interaction.guild.icon.url}")
    embed.set_footer(text="Made by Scott with ❤")
    embed.add_field(name="Tournament Starting", value=f"**<t:{timestamp}:R>**", inline=True)
    embed.add_field(name="Entry Fee", value=f"₹``{entry_fee}``", inline=True)
    embed.add_field(name="Maximum Teams", value=f"``{max_teams}``", inline=False)
    embed.add_field(name="Tournament ID", value=f"``{tournament_id}``", inline=True)
    embed.set_image(url=image.url)
    await interaction.followup.send(f"Created a Tournament with ID - {tournament_id}", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    await msg.edit(view=RegisterButton(category=category, spreadsheet_id=spreadsheet_id, entry_fee=entry_fee, tournament_name=tournament_name, tournament_id=tournament_id,msg=msg,max_teams=max_teams))
    tournament_data = {
        "tournament_name": tournament_name,
        "entry_fee": entry_fee,
        "details": details,
        "winner": None,
        "msg": msg.id,
        "channel_id": interaction.channel.id,
        "info_channel_id": info_channel.id,
        "spreadsheet_id": spreadsheet_id,
        "tournament_time": timestamp,
        "status": "running",
        "registerd_teams": 0,
        "teams": {}
    }
    save_tournament_data(tournament_id, tournament_data)

@bot.tree.command(name="close_registrations",description="Closes registrations for given tournament ID")
async def close_registrations(interaction: discord.Interaction, tournament_id: int):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ Only moderators can use this command!", ephemeral=True)
        return
    file_path = "tournaments.json"
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
                all_data = json.load(file)
    else:
        all_data = {}
    tournament_id_str = str(tournament_id)  
    if tournament_id_str in all_data:
        tournament_data = all_data[tournament_id_str]
        msg_id = tournament_data.get("msg")
        channel_id = tournament_data.get("channel_id")
        msg_id = tournament_data["msg"]
        tournament_data["status"] = "Registrations Closed"
        channel_id = tournament_data["channel_id"]
        channel = interaction.guild.get_channel(channel_id)
        msg = await channel.fetch_message(msg_id)
        await msg.edit(view=CloseRegistration())
    await interaction.response.send_message(f"Closed Registrations for tournament ID - ``{tournament_id}``", ephemeral=True)

@bot.tree.command(name="winner",description="Select the winner for a tournament")
async def winner(interaction: discord.Interaction, tournament_id: int, winner_team_id: str):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ Only moderators can use this command!", ephemeral=True)
        return
    file_path = "tournaments.json"
    try:
        winner_team_id = int(winner_team_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid team ID. Please enter a valid integer.", ephemeral=True)
        return

    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            all_data = json.load(file)
    else:
        all_data = {}

    teams_in_tournament = []
    winner_team_name = None
    for tourney_id, tournament_data in all_data.items():
        if str(tourney_id) == str(tournament_id):
            tournament_data["winner"] = winner_team_id
            tournament_data["status"] = f"Won By {team_name}"
            teams_in_tournament = tournament_data.get("teams", [])

    with open(file_path, "w") as file:
        json.dump(all_data, file, indent=4)

    for lb_path in [leaderboard_path, monthly_leaderboard_path]:
        leaderboard_data = load_leaderboard(lb_path)

        for team in teams_in_tournament.values():
            team_id = team["team_id"]
            team_name = team["team_name"]

            if team_id == winner_team_id:
                winner_team_name = team_name

            if team_name not in leaderboard_data:
                leaderboard_data[team_name] = {"wins": 0, "losses": 0, "points": 0, "played": 0}

            leaderboard_data[team_name]["played"] += 1
        for tourney_id, tournament_data in all_data.items():
            if str(tourney_id) == str(tournament_id):
                tournament_data["status"] = f"Won By {team_name}"
        if winner_team_name:
            leaderboard_data[winner_team_name]["wins"] += 1

        for team in teams_in_tournament.values():
            team_name = team["team_name"]
            if team_name != winner_team_name:
                leaderboard_data[team_name]["losses"] += 1

        for team_name, stats in leaderboard_data.items():
            stats["points"] = stats["wins"] - stats["losses"]

        save_leaderboard(lb_path, leaderboard_data)
    await interaction.response.send_message(f"Winner for tournament ID - ``{tournament_id}`` is **{winner_team_name}**!")
class LeaderboardView(View):
    def __init__(self, leaderboard_data, title, user, timeout=60):
        super().__init__(timeout=timeout)
        self.leaderboard_data = sorted(leaderboard_data.items(), key=lambda x: x[1]['points'], reverse=True)
        self.title = title
        self.user = user
        self.page = 0
        self.entries_per_page = 5
        self.update_buttons()

    def create_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(title=self.title, color=0xffffff,timestamp=datetime.datetime.now())
        start = self.page * self.entries_per_page
        end = start + self.entries_per_page
        for rank, (team, data) in enumerate(self.leaderboard_data[start:end], start=start + 1):
            embed.add_field(
                name=f"``#{rank}`` {team}",
                value=f"**{data['points']}** Points ({data['wins']} Wins, {data['losses']} Losses, {data['played']} Matches)",
                inline=False
            )
        embed.set_author(name="Swadeshi LAN",
            icon_url=interaction.guild.icon.url)
        embed.set_footer(text=f"Made by Scott With ❤ | Page {self.page + 1} of {self.total_pages()}")
        embed.set_thumbnail(url=f"{interaction.guild.icon.url}")
        
        return embed

    def total_pages(self):
        return max(1, len(self.leaderboard_data) // self.entries_per_page + (1 if len(self.leaderboard_data) % self.entries_per_page else 0))

    def update_buttons(self):
        self.children[0].disabled = self.page == 0
        self.children[1].disabled = self.page >= self.total_pages() - 1

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.gray, disabled=True)
    async def previous_page(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ You can't use these buttons!", ephemeral=True)
            return
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(interaction), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.gray, disabled=True)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ You can't use these buttons!", ephemeral=True)
            return
        if self.page < self.total_pages() - 1:
            self.page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(interaction), view=self)

@bot.tree.command(name="lb", description="Shows the leaderboard (weekly/monthly)")
async def leaderboard(interaction: discord.Interaction, timeframe: str):
    timeframe = timeframe.lower()
    if timeframe not in ["weekly", "monthly"]:
        await interaction.response.send_message("❌ Invalid option! Use `/lb weekly` or `/lb monthly`.", ephemeral=True)
        return

    file_path = leaderboard_path if timeframe == "weekly" else monthly_leaderboard_path
    leaderboard_data = load_json(file_path)

    if not leaderboard_data:
        await interaction.response.send_message(f"❌ No {timeframe} leaderboard data available.", ephemeral=True)
        return

    view = LeaderboardView(leaderboard_data, f"{timeframe.capitalize()} Leaderboard", interaction.user)
    await interaction.response.send_message(embed=view.create_embed(interaction), view=view)

@tasks.loop(hours=168)
async def reset_weekly_leaderboard():
    try:
        if os.path.exists(leaderboard_path):
            os.remove(leaderboard_path)
            print("Weekly leaderboard has been reset.")
    except Exception as e:
        print(f"Error resetting weekly leaderboard: {e}")

@tasks.loop(hours=720)
async def reset_monthly_leaderboard():
    try:
        if os.path.exists(monthly_leaderboard_path):
            os.remove(monthly_leaderboard_path)
            print("Monthly leaderboard has been reset.")
    except Exception as e:
        print(f"Error resetting monthly leaderboard: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You do not have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument.")
    else:
        await ctx.send("❌ An unexpected error occurred.")
        print(f"Error: {error}")

@commands.command(name="delcat")
@commands.has_permissions(manage_channels=True)
async def delcat(ctx, category_id: int):
    guild = ctx.guild
    category = discord.utils.get(guild.categories, id=category_id)

    if not category:
        await ctx.send(f"❌ No category found with ID `{category_id}`!")
        return

    # Delete all channels inside the category
    for channel in category.channels:
        await channel.delete()
    
    # Delete the category itself
    await category.delete()
    
    await ctx.send(f"✅ Deleted category `{category.name}` and all its channels!")

bot.add_command(delcat)

bot.run(DISCORD_TOKEN)
