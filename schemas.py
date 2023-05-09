from marshmallow import Schema, fields, ValidationError


class MessageSchema(Schema):
    text = fields.String(required=True)
    telegram_user_id = fields.Integer(required=True)
    is_bot = fields.Bool(required=True)
    first_name = fields.String(required=True)
    last_name = fields.String(required=True)
    username = fields.String(required=True)
    chat_id = fields.Integer(required=True)
    chat_type = fields.String(required=True)
    date = fields.Float(required=True)

    def validate_json(self, json_data : dict):
        '''
            This function validates the requests body.
                :param json_data: dict
                    The request body.
                :returns: dict, int
                    Returns the validated json or the errors in the json
                    and the status code.
        '''
        try:
            result = self.load(json_data)
        except ValidationError as err:
            return err.messages, 400
        return result, 200