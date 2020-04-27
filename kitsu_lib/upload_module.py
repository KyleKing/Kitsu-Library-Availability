"""Upload module."""

import time
from datetime import datetime

import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import pandas as pd
import plotly.express as px
from dash_charts.utils_app_modules import ModuleBase
from dash_charts.utils_callbacks import map_args, map_outputs

from .app_helpers import parse_uploaded_df
from .cache_helpers import CACHE_DIR, DBConnect


def show_toast(message, header, icon='warning', style=None, **toast_kwargs):
    """Create toast notification.

    Args:
        message: string body text
        header: string notification header
        icon: string name in `(primary,secondary,success,warning,danger,info,light,dark)`. Default is warning
        style: style dictionary. Default is the top right
        toast_kwargs: additional toast keyword arguments (such as `duration=5000`)

    Returns:
        dbc.Toast: toast notification from Dash Bootstrap Components library

    """
    if style is None:
        # Position in the top right (note: will occlude the tabs when open, could be moved elsewhere)
        style = {'position': 'fixed', 'top': 10, 'right': 10, 'width': 350, 'zIndex': 1900}
    return dbc.Toast(message, header=header, icon=icon, style=style, dismissable=True, **toast_kwargs)


def drop_to_upload(**upload_kwargs):
    """Create drop to upload element. Dashed box of the active area or a clickable link to use the file dialog.

    Based on dash documentation from: https://dash.plotly.com/dash-core-components/upload

    Args:
        upload_kwargs: keyword arguments for th dcc.Upload element. Children and style are reserved

    Returns:
        dcc.Upload: Dash upload element

    """
    return dcc.Upload(
        children=html.Div(['Drag and Drop or ', html.A('Select a File')]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px',
        },
        **upload_kwargs,
    )


class UploadModule(ModuleBase):
    """Module for user data upload."""

    id_upload = 'upload-drop-area'
    """Unique name for the upload component."""

    id_upload_output = 'upload-output'
    """Unique name for the div to contain output of the parse-upload."""

    all_ids = [id_upload, id_upload_output]
    """List of ids to register for this module."""

    def __init__(self, *args, **kwargs):
        """Initialize module."""  # noqa: DAR101
        super().__init__(*args, **kwargs)
        self.initialize_database()

    def initialize_database(self):
        """Create data members `self.database` and `self.user_table`."""
        self.database = DBConnect(CACHE_DIR / f'_placeholder_app-{self.name}.db')
        self.user_table = self.database.db.create_table(
            'users', primary_id='username', primary_type=self.database.db.types.text)
        self.inventory_table = self.database.db.create_table(
            'inventory', primary_id='table_name', primary_type=self.database.db.types.text)
        # Add default data to be used if user hasn't uploaded any test data
        self.default_table = self.database.db.create_table('default')
        if self.default_table.count() == 0:
            self.default_table.insert_many(px.data.tips().to_dict(orient='records'))

    def find_user(self, username):
        """Return the database row for the specified user.

        Args:
            username: string username

        Returns:
            dict: for row from table or None if no match

        """
        return self.user_table.find_one(username=username)

    def add_user(self, username):
        """Add the user to the table or update the user's information if already registered.

        Args:
            username: string username

        """
        now = time.time()
        if self.find_user(username):
            self.user_table.upsert({'username': username, 'last_loaded': now}, ['username'])
        else:
            self.user_table.insert({'username': username, 'creation': now, 'last_loaded': now})

    def upload_data(self, username, df_name, df_upload):
        """Store dataframe in database for specified user.

        Args:
            username: string username
            df_name: name of the stored dataframe
            df_upload: pandas dataframe to store

        """
        now = time.time()
        table_name = f'{username}-{df_name}-{int(now)}'
        table = self.database.db.create_table(table_name)
        try:
            table.insert_many(df_upload.to_dict(orient='records'))
        except Exception:
            table.drop()  # Delete the table if upload fails
            raise

        self.inventory_table.insert({'table_name': table_name, 'df_name': df_name, 'username': username,
                                    'creation': now})

    def get_data(self, table_name):
        """Retrieve stored data for specified dataframe name.

        Args:
            table_name: unique name of the table to retrieve

        Returns:
            pd.DataFrame: pandas dataframe retrieved from the database

        """
        table = self.database.db.load_table(table_name)
        return pd.DataFrame.from_records(table.all())

    def delete_data(self, table_name):
        """Remove specified data from the database.

        Args:
            table_name: unique name of the table to delete

        """
        self.database.db.load_table(table_name).drop()

    def return_layout(self, ids, storage_type='memory', **store_kwargs):
        """Return Dash application layout.

        Args:
            ids: `self.ids` from base application
            storage_type: `dcc.Store` storage type. Default is memory to clear on refresh
            store_kwargs: additional keyword arguments to pass to `dcc.Store`

        Returns:
            dict: Dash HTML object.

        """
        return html.Div([
            html.H2('File Upload'),
            html.P('Upload Tidy Data in CSV, Excel, or JSON format'),
            drop_to_upload(id=ids[self.get(self.id_upload)]),
            dcc.Loading(html.Div('PLACEHOLDER', id=ids[self.get(self.id_upload_output)]), type='circle'),
        ])

    def create_callbacks(self, parent):
        """Register callbacks to handle user interaction.

        Args:
            parent: parent instance (ex: `self`)

        """
        super().create_callbacks(parent)
        self.register_upload_handler(parent)

    def show_data(self, username):
        """Create Dash HTML to show the raw data loaded for the specified user.

        Args:
            username: string username

        Returns:
            dict: Dash HTML object

        """
        def format_table(df_name, username, creation, raw_df):
            return [
                html.H4(df_name),
                html.P(f'Uploaded by "{username}" on {datetime.fromtimestamp(creation)}'),
                dash_table.DataTable(
                    data=raw_df[:10].to_dict('records'),
                    columns=[{'name': i, 'id': i} for i in raw_df.columns[:10]],
                    style_cell={
                        'overflow': 'hidden',
                        'textOverflow': 'ellipsis',
                        'maxWidth': 0,
                    },
                ),
                html.Hr(),
            ]

        children = [html.Hr()]
        for row in self.inventory_table.find(username=username):
            df_upload = self.get_data(row['table_name'])
            children.extend(format_table(row['df_name'], row['username'], row['creation'], df_upload))
        children.extend(
            format_table('Default', 'N/A', time.time(), pd.DataFrame.from_records(self.default_table.all())))
        return html.Div(children)

    def register_upload_handler(self, parent):
        """Register callbacks to handle user interaction.

        Args:
            parent: parent instance (ex: `self`)

        """
        outputs = [(self.get(self.id_upload_output), 'children')]
        inputs = [(self.get(self.id_upload), 'contents')]
        states = [(self.get(self.id_upload), 'filename'), (self.get(self.id_upload), 'last_modified')]

        @parent.callback(outputs, inputs, states)
        def upload_handler(*raw_args):
            a_in, a_state = map_args(raw_args, inputs, states)
            b64_file = a_in[self.get(self.id_upload)]['contents']
            filename = a_state[self.get(self.id_upload)]['filename']
            timestamp = a_state[self.get(self.id_upload)]['last_modified']
            username = 'username'  # TODO: IMPLEMENT

            child_output = []
            try:
                if b64_file is not None:
                    df_upload = parse_uploaded_df(b64_file, filename, timestamp)
                    df_upload = df_upload.dropna(axis='columns')  # FIXME: Need to better handle NaN values
                    self.add_user(username)
                    self.upload_data(username, filename, df_upload)

            except Exception as error:
                child_output.extend([
                    show_toast(f'{error}', 'Upload Error', icon='danger'),
                    dcc.Markdown(f'### Upload Error\n\n{type(error)}\n\n```\n{error}\n```'),
                ])

            child_output.append(self.show_data(username))

            return map_outputs(outputs, [(self.get(self.id_upload_output), 'children', html.Div(child_output))])
