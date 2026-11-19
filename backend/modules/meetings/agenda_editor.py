from modules.meetings.meeting_tool import MeetingTool


class AgendaEditor(MeetingTool):
    """Modifie l'ordre du jour d'une réunion (les points à aborder)."""

    def __init__(self, meetings_service):
        super().__init__(meetings_service=meetings_service)
        self.max_point_length = 200


    def clean_point(self, point):

        point = " ".join((point or "").split())[:self.max_point_length]

        if not point:
            raise ValueError("Un point de l'ordre du jour ne peut pas être vide.")

        return point


    def check_size(self, points):

        if len(points) > self.meetings_service.max_agenda_items:
            raise ValueError(
                f"L'ordre du jour peut avoir {self.meetings_service.max_agenda_items} points au maximum."
            )


    def set_points(self, meeting_id, points):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        clean_points = [self.clean_point(point=point) for point in points]
        self.check_size(points=clean_points)

        meeting["agenda"] = clean_points
        self.save_meeting(meeting_id=meeting_id)

        return meeting["agenda"]


    def add_point(self, meeting_id, point, position=None):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        points = list(meeting["agenda"])
        index = len(points) if position is None else max(0, min(position - 1, len(points)))
        points.insert(index, self.clean_point(point=point))
        self.check_size(points=points)

        meeting["agenda"] = points
        self.save_meeting(meeting_id=meeting_id)

        return meeting["agenda"]


    def remove_point(self, meeting_id, position):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        if not 1 <= position <= len(meeting["agenda"]):
            raise ValueError("Ce numéro ne correspond à aucun point de l'ordre du jour.")

        meeting["agenda"].pop(position - 1)
        self.save_meeting(meeting_id=meeting_id)

        return meeting["agenda"]