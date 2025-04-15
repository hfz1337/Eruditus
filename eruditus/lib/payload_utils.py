import os
import re
import aiofiles
import re

from io import BytesIO

import discord
from discord import app_commands, Interaction, File

# Search for content in intruder files
async def search_intruder_content(intruder_dir: str, query2: str) -> list[str]:
    matched_files = []
    for root, _, files in os.walk(intruder_dir):
        for file in files:
            if file.endswith(".txt") or file.endswith(".md"):
                file_path = os.path.join(root, file)
                async with aiofiles.open(file_path, mode="r", encoding="utf-8", errors="ignore") as f:
                    content = await f.read()
                    if query2.lower() in content.lower():
                        matched_files.append(file)
    return matched_files

# Extract code payloads from markdown files
async def extract_payloads_from_file(file_path: str) -> list[str]:
    async with aiofiles.open(file_path, mode="r", encoding="utf-8", errors="ignore") as f:
        content = await f.read()

    blocks = []
    current_heading = None
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        heading_match = re.match(r"^(##+)\s+(.*)", line)
        if heading_match:
            current_heading = heading_match.group(2).strip()
            i += 1
            continue

        if line.strip().startswith("```"):
            lang = re.match(r"```(\w+)?", line.strip())
            code_lang = lang.group(1) if lang else ""
            i += 1
            code_content = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_content.append(lines[i])
                i += 1
            i += 1
            code_block = "\n".join(code_content).strip()
            if current_heading and code_block:
                blocks.append(f"**{current_heading}**\n```{code_lang}\n{code_block}\n```")
            continue

        if "|" in line and "---" in line:
            if i >= 1:
                table_heading = current_heading or "Table Payload"
                headers = [h.strip() for h in lines[i - 1].split("|") if h.strip()]
                i += 1
                rows = []
                while i < len(lines) and "|" in lines[i]:
                    values = [v.strip() for v in lines[i].split("|") if v.strip()]
                    if len(values) == len(headers):
                        rows.append(dict(zip(headers, values)))
                    i += 1
                if rows:
                    table_output = f"**{table_heading}**"
                    for row in rows:
                        items = ', '.join(f"{k}: {v}" for k, v in row.items())
                        table_output += f"\n{items}"
                    blocks.append(table_output)
            continue

        i += 1

    return blocks

# Autocomplete payload topics
async def autocomplete_payload(interaction: Interaction, current: str, base_dir: str) -> list[app_commands.Choice[str]]:
    if len(current) < 2:
        return []

    current = current.lower()
    choices = set()

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".md"):
                name = os.path.basename(os.path.dirname(os.path.join(root, file)))
                if current in name.lower():
                    choices.add(name)
            if len(choices) >= 25:
                break

    return [app_commands.Choice(name=name, value=name) for name in choices]

# Autocomplete for type
async def autocomplete_type(interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
    options = ["payload", "file", "intruder"]
    return [
        app_commands.Choice(name=opt, value=opt)
        for opt in options if current.lower() in opt.lower()
    ]

# Send long messages in chunks, preserving code blocks and avoiding loss
async def send_long_message(destination, content: str, max_length: int = 2000):
    processed_content = ""
    in_code_block = False
    code_block_start_marker = None
    
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        if line.strip().startswith('```'):
            if in_code_block:
                in_code_block = False
                code_block_start_marker = None
                processed_content += line + '\n'
            else:
                in_code_block = True
                code_block_start_marker = line.strip()
                processed_content += line + '\n'
        elif in_code_block and '```' in line:
            processed_content += line.replace('```', '(triple backticks)') + '\n'
        else:
            processed_content += line + '\n'
        
        i += 1

    sections = []
    current_section = []
    in_code_block = False
    code_language = ""
    
    lines = processed_content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]

        if line.strip().startswith('```'):
            if in_code_block:
                current_section.append(line)
                sections.append(('code', code_language, current_section))
                current_section = []
                in_code_block = False
            else:
                if current_section:
                    sections.append(('text', '', current_section))
                current_section = [line]
                in_code_block = True
                code_language = line.strip()[3:].strip()
        elif not in_code_block and line.strip().startswith('**') and '**' in line.strip()[2:]:
            if current_section:
                sections.append(('text', '', current_section))
                current_section = [line]
            else:
                current_section = [line]

            if i + 1 < len(lines) and lines[i+1].strip() in ['javascript', 'python', 'html', 'css']:
                current_section.append(lines[i+1])
                i += 1
                
            sections.append(('header', '', current_section))
            current_section = []
        else:
            current_section.append(line)
        
        i += 1

    if current_section:
        if in_code_block:
            sections.append(('code', code_language, current_section))
        else:
            sections.append(('text', '', current_section))

    messages = []
    current_message = ""
    
    for section_type, language, section_lines in sections:
        while section_lines and not section_lines[0].strip():
            section_lines.pop(0)
        while section_lines and not section_lines[-1].strip():
            section_lines.pop()
            
        if not section_lines:
            continue 
            
        section_text = '\n'.join(section_lines)
        
        if len(current_message) + len(section_text) + (1 if current_message else 0) > max_length:
            if len(section_text) > max_length:
                if current_message:
                    messages.append(current_message)
                    current_message = ""

                if section_type == 'code':
                    remaining_lines = section_lines.copy()
                    chunk_lines = []
                    chunk_size = 0
                    
                    first_line = remaining_lines.pop(0)
                    chunk_lines.append(first_line)
                    chunk_size = len(first_line) + 1
                    
                    while remaining_lines:
                        line = remaining_lines[0]
                        line_size = len(line) + 1

                        if chunk_size + line_size > max_length - 4:
                            chunk_lines.append("```")
                            messages.append('\n'.join(chunk_lines))

                            chunk_lines = [f"```{language}"]
                            chunk_size = len(chunk_lines[0]) + 1

                        chunk_lines.append(line)
                        chunk_size += line_size
                        remaining_lines.pop(0)

                    if not chunk_lines[-1].strip() == "```":
                        chunk_lines.append("```")
                    
                    messages.append('\n'.join(chunk_lines))
                else:
                    remaining = section_text
                    while remaining:
                        messages.append(remaining[:max_length])
                        remaining = remaining[max_length:]
            else:
                messages.append(current_message)
                current_message = section_text
        else:
            if current_message:
                current_message += '\n' + section_text
            else:
                current_message = section_text
    
    if current_message:
        messages.append(current_message)
    
    # Send each message
    for msg in messages:
        msg = msg.strip()
        if msg: 
            if len(msg) > max_length:
                chunks = [msg[i:i+max_length] for i in range(0, len(msg), max_length)]
                for chunk in chunks:
                    try:
                        await destination.send(chunk)
                    except Exception as e:
                        print(f"Error sending message chunk: {str(e)}")
            else:
                try:
                    await destination.send(msg)
                except Exception as e:
                    print(f"Error sending message: {str(e)}")
                    try:
                        await destination.send(f"Error sending message ({len(msg)} chars). Some content may be missing.")
                    except:
                        pass  
            
# Send paginated messages
def format_page(lines: list[str], is_continued: bool = False, continues_to_next: bool = False) -> str:
    parts = []
    i = 0

    if is_continued and lines:
        code_block_lines = []
        while i < len(lines) and not (lines[i].startswith("+ ") or re.match(r'^\s*\*\*(.+?)\*\*\s*$', lines[i])):
            code_block_lines.append(lines[i])
            i += 1
        
        if code_block_lines:
            code_content = "".join(code_block_lines).rstrip("\n")
            code_content = code_content.replace("```", "(3 backticks)")
            parts.append(f"```md\n{code_content}\n```\n")

    while i < len(lines):
        line = lines[i]

        if line.startswith("+ ") or re.match(r'^\s*\*\*(.+?)\*\*\s*$', line):
            if line.startswith("+ "):
                header_text = line[2:].strip()
            else:
                match = re.match(r'^\s*\*\*(.+?)\*\*\s*$', line)
                header_text = match.group(1) if match else line.strip()
            
            parts.append(f"**{header_text}**\n")
            i += 1

            code_block_lines = []
            code_block_ends_page = False
            
            while i < len(lines) and not (lines[i].startswith("+ ") or re.match(r'^\s*\*\*(.+?)\*\*\s*$', lines[i])):
                code_block_lines.append(lines[i])
                i += 1

            if i >= len(lines) and continues_to_next:
                code_block_ends_page = True

            if code_block_lines:
                code_content = "".join(code_block_lines).rstrip("\n")
                code_content = code_content.replace("```", "(3 backticks)")
                parts.append(f"```md\n{code_content}\n```\n")
        else:
            parts.append(line)
            i += 1

    if continues_to_next:
        parts.append("(continued in next page...)\n")
    
    return "".join(parts)

def calculate_formatted_length(lines: list[str], is_continued: bool = False, continues_to_next: bool = False) -> int:
    total_length = 0
    i = 0

    if is_continued and lines:
        code_length = 0
        while i < len(lines) and not (lines[i].startswith("+ ") or re.match(r'^\s*\*\*(.+?)\*\*\s*$', lines[i])):
            line = lines[i].replace("```", "(3 backticks)")
            code_length += len(line)
            i += 1

        if code_length > 0:
            total_length += code_length + 9 
    
    while i < len(lines):
        line = lines[i]

        if line.startswith("+ ") or re.match(r'^\s*\*\*(.+?)\*\*\s*$', line):
            if line.startswith("+ "):
                header_text = line[2:].strip()
            else:
                match = re.match(r'^\s*\*\*(.+?)\*\*\s*$', line)
                header_text = match.group(1) if match else line.strip()
            
            total_length += len(f"**{header_text}**\n")
            i += 1

            code_length = 0
            while i < len(lines) and not (lines[i].startswith("+ ") or re.match(r'^\s*\*\*(.+?)\*\*\s*$', lines[i])):
                line = lines[i].replace("```", "(3 backticks)")
                code_length += len(line)
                i += 1

            if code_length > 0:
                total_length += code_length + 9  
        else:
            total_length += len(line)
            i += 1

    if continues_to_next:
        total_length += len("(continued in next page...)\n")
    
    return total_length

def split_into_pages(text: str, max_length: int = 1900) -> list[tuple[list[str], bool, bool]]:
    raw_lines = []
    for line in text.splitlines(keepends=True):
        if line.strip() == "```" or line.strip().startswith("```"):
            continue
        raw_lines.append(line)

    pages = []
    current = []
    footer_buffer = len("\nPage 99/99")
    
    i = 0
    in_code_block = False
    code_block_continues = False
    
    while i < len(raw_lines):
        line = raw_lines[i]

        is_header = line.startswith("+ ") or re.match(r'^\s*\*\*(.+?)\*\*\s*$', line)

        if is_header and current:
            formatted_length = calculate_formatted_length(
                current, 
                is_continued=code_block_continues if pages else False,
                continues_to_next=False
            )
            
            if formatted_length + footer_buffer > max_length:
                pages.append((current.copy(), code_block_continues if pages else False, False))
                current = [line]
                i += 1
                code_block_continues = False
                in_code_block = True 
            else:
                current.append(line)
                i += 1
                in_code_block = True  
        else:
            if in_code_block and current:
                candidate = current + [line]
                formatted_length = calculate_formatted_length(
                    candidate,
                    is_continued=code_block_continues if pages else False,
                    continues_to_next=False
                )
                
                if formatted_length + footer_buffer > max_length:
                    pages.append((current.copy(), code_block_continues if pages else False, True))
                    current = [line]
                    i += 1
                    code_block_continues = True 
                else:
                    current.append(line)
                    i += 1
            else:
                current.append(line)
                i += 1

                if is_header:
                    in_code_block = True

    if current:
        pages.append((current.copy(), code_block_continues if pages else False, False))
    
    return pages

async def send_paginated(interaction: discord.Interaction, content: str):
    raw_pages = split_into_pages(content, max_length=1900)
    total = len(raw_pages)
    if total == 0:
        return await interaction.followup.send("No content to display.")

    class Pager(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.page = 0
            self.msg: discord.Message | None = None

        async def show(self, inter: discord.Interaction):
            page_content, is_continued, continues_to_next = raw_pages[self.page]
            body = format_page(page_content, is_continued, continues_to_next)
            
            final_text = f"{body}\nPage {self.page+1}/{total}"
            if len(final_text) > 2000:
                final_text = final_text[:1950] + "...\nPage {self.page+1}/{total}"
            
            if self.msg:
                await self.msg.edit(content=final_text, view=self)
            else:
                self.msg = await inter.followup.send(final_text, view=self)

        @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
        async def prev(self, inter2: discord.Interaction, _):
            if self.page > 0:
                self.page -= 1
                await self.show(inter2)
            await inter2.response.defer()

        @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
        async def next(self, inter2: discord.Interaction, _):
            if self.page < total - 1:
                self.page += 1
                await self.show(inter2)
            await inter2.response.defer()

    pager = Pager()
    await pager.show(interaction)

# Ask user how to display payloads
async def ask_user_view_mode(interaction: discord.Interaction, content: str):
    class AskView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.choice = None

        @discord.ui.button(label="🧾 Paginated", style=discord.ButtonStyle.primary)
        async def paginated_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            await send_paginated(interaction, content)

        @discord.ui.button(label="🧱 Message", style=discord.ButtonStyle.secondary)
        async def msg_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            await send_long_message(interaction.followup, content)

        @discord.ui.button(label="📄 .txt File", style=discord.ButtonStyle.success)
        async def txt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            await send_as_txt_file(interaction, content)

    view = AskView()
    await interaction.followup.send("This payload is large. How do you want to view it?", view=view)
    await view.wait()

async def send_as_txt_file(interaction, content: str):
    file = File(BytesIO(content.encode()), filename="payloads.txt")
    await interaction.followup.send("📄 Here’s the payload content as a `.txt` file:", file=file)