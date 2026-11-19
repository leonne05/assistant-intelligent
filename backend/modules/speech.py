import re


class SpokenTextBuilder:
    """Prépare un texte pour qu'une voix puisse le lire (sans symboles, dates en toutes lettres).

    Ce module ne fabrique pas de voix : la voix de JARVIS (module commun) lit le texte obtenu.
    """

    def __init__(self):
        self.months = [
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        ]


    def say_date(self, match):

        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))

        if not 1 <= month <= 12:
            return match.group(0)

        day_text = "1er" if day == 1 else str(day)

        return f"{day_text} {self.months[month - 1]} {year}"


    def build(self, markdown):

        sentences = []

        for line in markdown.splitlines():
            line = line.strip()

            if not line:
                continue

            is_title = line.startswith("#")
            line = re.sub(r"^#+\s*", "", line)
            line = re.sub(r"^[-*•]\s+", "", line)
            line = line.replace("**", "").replace("__", "").replace("`", "")
            line = re.sub(r"(\d{4})-(\d{2})-(\d{2})", self.say_date, line)
            line = line.strip()

            if not line:
                continue

            if line[-1] not in ".!?:":
                line += "."

            sentences.append(line)

            if is_title:
                sentences.append("")

        return "\n".join(sentences)