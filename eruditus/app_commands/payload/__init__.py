import os
import asyncio

from discord.ext import commands
from discord import app_commands, File, Interaction

from lib import payload_utils 
from config import PAYLOADS_DIR, PAYLOADS_VIEW

async def query1_autocomplete(interaction: Interaction, current: str):
    return await payload_utils.autocomplete_payload(interaction, current, PAYLOADS_DIR)

async def type_autocomplete(interaction: Interaction, current: str):
    return await payload_utils.autocomplete_type(interaction, current)

class Payload(app_commands.Command):
    def __init__(self):
        @app_commands.describe(
            query1="Main topic (e.g. SQL, XSS, SSTI)",
            query2="Optional keyword (e.g. SELECT, alert)",
            type="payload (default), file, or intruder"
        )
        @app_commands.autocomplete(
            query1=query1_autocomplete,
            type=type_autocomplete
        )
        async def callback(
            interaction: Interaction,
            query1: str,
            query2: str = "",
            type: str = "payload"
        ):
            await interaction.response.defer()

            matched_dirs = []
            for root, _, files in os.walk(PAYLOADS_DIR):
                for file in files:
                    if file.endswith(".md") and query1.lower() in root.lower():
                        matched_dirs.append(os.path.dirname(os.path.join(root, file)))
                        break

            if not matched_dirs:
                await interaction.followup.send(f"❌ No topic found matching `{query1}`.")
                return

            base_dir = matched_dirs[0]

            if type.lower() == "file":
                files_dir = os.path.join(base_dir, "Files")
                if not os.path.isdir(files_dir):
                    await interaction.followup.send("❌ No `Files` directory found for this topic.")
                    return

                all_files = os.listdir(files_dir)
                if query2:
                    all_files = [f for f in all_files if query2.lower() in f.lower()]
                if not all_files:
                    await interaction.followup.send("❌ No matching files found.")
                    return

                header = f"🔍 Available Files in `{query1}` Insecure Files"
                
                file_list = []
                for f in all_files:
                    if f.endswith(('.jpg', '.png', '.gif', '.jpeg')):
                        icon = "🖼️"
                    elif f.endswith(('.py', '.pyc', '.pyw', '.pyx')):
                        icon = "📄"
                    elif f.endswith(('.html', '.htm')):
                        icon = "📄"
                    elif f.endswith(('.php', '.php3', '.php5')):
                        icon = "📄"
                    elif f.endswith('.zip'):
                        icon = "📦"
                    elif f == ".htaccess":
                        icon = "⚙️"
                    else:
                        icon = "📄"
                    
                    file_list.append(f"{icon} `{f}`")
                
                chunks = []
                current_chunk = [header]
                current_length = len(header)
                
                for file_entry in file_list:
                    if current_length + len(file_entry) + 2 > 1900: 
                        chunks.append("\n".join(current_chunk))
                        current_chunk = [f"🔍 Available Files in `{query1}` (continued)"]
                        current_length = len(current_chunk[0])
                    
                    current_chunk.append(file_entry)
                    current_length += len(file_entry) + 1 
                
                if current_chunk:
                    chunks.append("\n".join(current_chunk))

                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:
                        chunk += "\n\n📩 Reply with the filename to receive the file."
                    
                    await interaction.followup.send(chunk)

                def check(m):
                    return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

                try:
                    response = await interaction.client.wait_for("message", timeout=60, check=check)
                    requested_file = response.content.strip()
                    file_path = os.path.join(files_dir, requested_file)
                    if os.path.isfile(file_path):
                        await interaction.followup.send(f"Here is your file `{requested_file}`:", file=File(file_path))
                    else:
                        await interaction.followup.send("❌ File not found.")
                except asyncio.TimeoutError:
                    await interaction.followup.send("⌛ Timeout. You didn’t reply in time.")
                return

            if type.lower() == "intruder":
                intruder_dir = os.path.join(base_dir, "Intruders")
                if not os.path.isdir(intruder_dir):
                    await interaction.followup.send("❌ No `Intruder` directory found.")
                    return

                if query2:
                    matched_files = await payload_utils.search_intruder_content(intruder_dir, query2)
                    if not matched_files:
                        await interaction.followup.send("❌ No matching intruder content found.")
                        return
                    
                    intruder_list = "\n".join(f"🎯 `{f}`" for f in matched_files)
                    await interaction.followup.send(f"**Intruder Payloads in `{query1}` with `{query2}` text in it:**\n{intruder_list}\n\n📩 Reply with the filename to get it.")
                    def check(m):
                        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

                    try:
                        response = await interaction.client.wait_for("message", timeout=60, check=check)
                        requested_file = response.content.strip()
                        file_path = os.path.join(intruder_dir, requested_file)
                        if os.path.isfile(file_path):
                            await interaction.followup.send(f"Here’s your intruder file `{requested_file}`:", file=File(file_path))
                        else:
                            await interaction.followup.send("❌ File not found.")
                    except asyncio.TimeoutError:
                        await interaction.followup.send("⌛ Timeout. You didn’t reply in time.")
                    return                    

                intruder_files = os.listdir(intruder_dir)
                if not intruder_files:
                    await interaction.followup.send("❌ No intruder files found.")
                    return

                intruder_list = "\n".join(f"🎯 `{f}`" for f in intruder_files)
                msg = await interaction.followup.send(
                    f"**Intruder Payloads in `{query1}`**\n{intruder_list}\n\n📩 Reply with the filename to get it."
                )

                def check(m):
                    return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

                try:
                    response = await interaction.client.wait_for("message", timeout=60, check=check)
                    requested_file = response.content.strip()
                    file_path = os.path.join(intruder_dir, requested_file)
                    if os.path.isfile(file_path):
                        await interaction.followup.send(f"Here’s your intruder file `{requested_file}`:", file=File(file_path))
                    else:
                        await interaction.followup.send("❌ File not found.")
                except asyncio.TimeoutError:
                    await interaction.followup.send("⌛ Timeout. You didn’t reply in time.")
                return

            # Default: payload
            all_payloads = []
            for root, _, files in os.walk(base_dir):
                for file in files:
                    if file.endswith(".md"):
                        file_path = os.path.join(root, file)
                        payloads = await payload_utils.extract_payloads_from_file(file_path)
                        if query2:
                            payloads = [p for p in payloads if query2.lower() in p.lower()]
                        all_payloads.extend(payloads)

            if not all_payloads:
                await interaction.followup.send("❌ No matching payloads found.")
                return

            full_payload = "\n\n".join(all_payloads)

            if PAYLOADS_VIEW == "page":
                await payload_utils.send_paginated(interaction, full_payload)
            elif PAYLOADS_VIEW == "msg":
                await payload_utils.send_long_message(interaction.followup, full_payload)
            elif PAYLOADS_VIEW == "txt":
                await payload_utils.send_as_txt_file(interaction, full_payload)
            else:
                await payload_utils.ask_user_view_mode(interaction, full_payload)

        super().__init__(
            name="payload",
            description="Search payloads, files, or intruder wordlists from PayloadsAllTheThings.",
            callback=callback,
        )
