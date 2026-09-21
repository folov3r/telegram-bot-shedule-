import logging
from docx import Document
from cache_schedule import schedule_cache

allowed_groups = [
    "10",
    "11.1",
    "11.2",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "КСК-1",
    "ОП-1",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "КСК-2",
    "ОП-2",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "КСК-3",
    "ОП-3",
    "40.1",
    "40.2",
    "41",
    "42",
    "43",
    "44",
    "45",
    "101",
    "102",
    "201",
    "202",
    "203",
]

def validate_and_correct_group(user_input: str) -> tuple[str | None, bool]:
    user_input = user_input.upper()

    if user_input in allowed_groups:
        return user_input, True

    for group in allowed_groups:
        if user_input.replace(" ", "-") == group or user_input == group.replace(
            "-", " "
        ):
            return group, True

    if user_input.isdigit():
        for group in allowed_groups:
            if group.isdigit() and group == user_input:
                return group, True

    return None, False

def format_teacher_schedule(teacher_schedule_data: dict, teacher_name: str, date_label: str) -> str | None:
    if teacher_name not in teacher_schedule_data:
        return None
    all_entries = []
    for group, entries in teacher_schedule_data[teacher_name].items():
        for entry in entries.split("\n"):
            pair_number = int(entry.split("|")[1].split(".")[0])
            all_entries.append((pair_number, group, entry))

    all_entries.sort(key=lambda x: x[0])

    grouped_entries = []
    current_group = None
    current_entries = []
    for pair_number, group, entry in all_entries:
        if group == current_group:
            current_entries.append(entry)
        else:
            if current_group:
                grouped_entries.append((current_group, current_entries))
            current_group = group
            current_entries = [entry]
    if current_group:
        grouped_entries.append((current_group, current_entries))

    response = f"Ваше расписание {date_label}:\n\n|Пара| |Кабинет|\n\n"
    for group, entries in grouped_entries:
        response += f"С группой {group}:\n"
        response += "\n".join(entries) + "\n\n"
    return response


def process_schedule_file(file_path: str) -> tuple[dict | None, dict | None]:
    target_date = file_path.split("/")[-1]

    if target_date in schedule_cache:
        logging.info(f"Используется кеш для даты {target_date}")
        return schedule_cache[target_date]

    schedule_data = {}
    teacher_schedule_data = {}
    doc = Document(file_path)
    current_group = None

    def add_schedule_entry(group: str, pair_number: str, subject: str, teacher: str | None, room: str | None) -> None:
        if group not in schedule_data:
            schedule_data[group] = []

        if teacher and teacher not in teacher_schedule_data:
            teacher_schedule_data[teacher] = {}

        if subject in ["Практика", "Разговоры о важном", "Сессия"]:
            schedule_entry = f"|{pair_number} {subject}|"
        elif subject or teacher or room:
            schedule_entry = f"|{pair_number} {subject}| |{teacher}| |{room}|"
        else:
            schedule_entry = f"|{pair_number} Нет пары|"

        schedule_data[group].append((pair_number, schedule_entry))

        if teacher:
            if group not in teacher_schedule_data[teacher]:
                teacher_schedule_data[teacher][group] = []
            teacher_entry = f"|{pair_number} {subject}| |{room}|"
            teacher_schedule_data[teacher][group].append((pair_number, teacher_entry))

    try:
        for table in doc.tables:
            rows = list(table.rows)
            for i, row in enumerate(rows):
                cells = [cell.text.strip() if cell.text else "" for cell in row.cells]
                if len(cells) >= 3:
                    if cells[0]:
                        current_group = cells[0]
                    elif (
                        not cells[0]
                        and not cells[1]
                        and not cells[2]
                        and not cells[3]
                        and not cells[4]
                    ):
                        current_group = None
                        continue

                    if current_group:
                        teacher = cells[3] if len(cells) > 3 else None
                        room = cells[4] if len(cells) > 4 else None
                        add_schedule_entry(
                            current_group, cells[1], cells[2], teacher, room
                        )

        for group in schedule_data:
            pairs = schedule_data[group]
            last_filled_index = -1
            for i, (pair_number, entry) in enumerate(pairs):
                if not entry.endswith("Нет пары|"):
                    last_filled_index = i

            if last_filled_index != -1:
                schedule_data[group] = pairs[: last_filled_index + 1]

        for group in schedule_data:
            schedule_data[group] = "\n".join(
                [entry[1] for entry in schedule_data[group]]
            )

        for teacher in teacher_schedule_data:
            for group in teacher_schedule_data[teacher]:
                teacher_schedule_data[teacher][group].sort(
                    key=lambda x: (
                        int(x[0].split(".")[0]) if x[0].split(".")[0].isdigit() else 0
                    )
                )
                teacher_schedule_data[teacher][group] = "\n".join(
                    [entry[1] for entry in teacher_schedule_data[teacher][group]]
                )

        schedule_cache[target_date] = (schedule_data, teacher_schedule_data)
        logging.info(f"Данные для даты {target_date} добавлены в кеш")

        return schedule_data, teacher_schedule_data

    except Exception as e:
        logging.error(f"Ошибка при обработке файла: {e}")
        return None, None
