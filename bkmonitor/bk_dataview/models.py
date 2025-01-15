# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.db import models

from .settings import APP_LABEL


class User(models.Model):
    id = models.BigAutoField(primary_key=True)
    version = models.IntegerField(default=0)
    login = models.CharField(unique=True, max_length=190)
    email = models.CharField(unique=True, max_length=190)
    name = models.CharField(max_length=255, blank=True, null=True, default="")
    password = models.CharField(max_length=255, blank=True, null=True)
    salt = models.CharField(max_length=50, blank=True, null=True)
    rands = models.CharField(max_length=50, blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True, default="")
    org_id = models.BigIntegerField(default=1)
    is_admin = models.BooleanField(default=False)
    email_verified = models.BooleanField(blank=True, null=True, default=False)
    theme = models.CharField(max_length=255, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    help_flags1 = models.BigIntegerField(default=0)
    last_seen_at = models.DateTimeField(blank=True, null=True)
    is_disabled = models.BooleanField(default=False)
    is_service_account = models.BooleanField(default=False)

    class Meta:
        managed = False
        app_label = APP_LABEL
        db_table = "user"
        indexes = [models.Index(fields=["login", "email"])]


class UserRole(models.Model):
    id = models.BigAutoField(primary_key=True)
    org_id = models.BigIntegerField()
    user_id = models.BigIntegerField()
    role_id = models.BigIntegerField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        app_label = APP_LABEL
        db_table = "user_role"
        unique_together = (("org_id", "user_id", "role_id"),)
        indexes = [
            models.Index(fields=["org_id"]),
            models.Index(fields=["user_id"]),
        ]


class Org(models.Model):
    id = models.BigAutoField(primary_key=True)
    version = models.IntegerField(default=0)
    name = models.CharField(unique=True, max_length=190)
    address1 = models.CharField(max_length=255, blank=True, null=True, default="")
    address2 = models.CharField(max_length=255, blank=True, null=True, default="")
    city = models.CharField(max_length=255, blank=True, null=True, default="")
    state = models.CharField(max_length=255, blank=True, null=True, default="")
    zip_code = models.CharField(max_length=50, blank=True, null=True, default="")
    country = models.CharField(max_length=255, blank=True, null=True, default="")
    billing_email = models.CharField(max_length=255, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        app_label = APP_LABEL
        db_table = "org"


class OrgUser(models.Model):
    id = models.BigAutoField(primary_key=True)
    org_id = models.BigIntegerField()
    user_id = models.BigIntegerField()
    role = models.CharField(max_length=20)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        app_label = APP_LABEL
        db_table = "org_user"
        unique_together = (("org_id", "user_id"),)


class DataSource(models.Model):
    id = models.BigAutoField(primary_key=True)
    org_id = models.BigIntegerField()
    version = models.IntegerField(default=0)
    type = models.CharField(max_length=255)
    name = models.CharField(max_length=190)
    access = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True, null=True, default="")
    password = models.CharField(max_length=255, blank=True, null=True, default="")
    user = models.CharField(max_length=255, blank=True, null=True, default="")
    database = models.CharField(max_length=255, blank=True, null=True, default="")
    basic_auth = models.BooleanField(default=False)
    basic_auth_user = models.CharField(max_length=255, blank=True, null=True, default="")
    basic_auth_password = models.CharField(max_length=255, blank=True, null=True, default="")
    is_default = models.BooleanField(default=False)
    json_data = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    with_credentials = models.BooleanField(default=False)
    secure_json_data = models.TextField(blank=True, null=True, default="")
    read_only = models.BooleanField(default=False)
    uid = models.CharField(max_length=40, blank=True, default="0")

    def __str__(self):
        return f"<{self.id}, {self.name}>"

    class Meta:
        managed = False
        app_label = APP_LABEL
        db_table = "data_source"
        unique_together = (("org_id", "name"),)


class Dashboard(models.Model):
    id = models.BigAutoField(primary_key=True)
    version = models.IntegerField()
    slug = models.CharField(max_length=189)
    title = models.CharField(max_length=189)
    data = models.TextField()
    org_id = models.BigIntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    updated_by = models.IntegerField(blank=True, null=True)
    created_by = models.IntegerField(blank=True, null=True)
    gnet_id = models.BigIntegerField(blank=True, null=True)
    plugin_id = models.CharField(max_length=189, blank=True, null=True)
    folder_id = models.BigIntegerField()
    is_folder = models.IntegerField()
    has_acl = models.BooleanField(default=False)
    uid = models.CharField(max_length=40, blank=True, null=True)
    is_public = models.BooleanField(default=False)

    class Meta:
        managed = False
        app_label = APP_LABEL
        db_table = "dashboard"
        unique_together = (
            ("org_id", "folder_id", "title"),
            ("org_id", "uid"),
        )


class Team(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=190)
    org_id = models.BigIntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    email = models.EmailField(blank=True, null=True)

    class Meta:
        db_table = "team"
        app_label = APP_LABEL
        managed = False
        unique_together = (("org_id", "name"),)
        indexes = [models.Index(fields=["org_id"])]


class TeamMember(models.Model):
    id = models.BigAutoField(primary_key=True)
    org_id = models.BigIntegerField()
    team_id = models.ForeignKey(Team, on_delete=models.CASCADE)
    user_id = models.BigIntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    external = models.BooleanField(blank=True, null=True)
    permission = models.SmallIntegerField(blank=True, null=True)

    class Meta:
        db_table = "team_member"
        app_label = APP_LABEL
        managed = False
        unique_together = (("org_id", "team_id", "user_id"),)
        indexes = [
            models.Index(fields=["org_id"]),
            models.Index(fields=["team_id"]),
        ]


class TeamRole(models.Model):
    id = models.BigAutoField(primary_key=True)
    org_id = models.BigIntegerField()
    team_id = models.BigIntegerField()
    role_id = models.BigIntegerField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "team_role"
        app_label = APP_LABEL
        managed = False
        unique_together = (("org_id", "team_id", "role_id"),)
        indexes = [
            models.Index(fields=["org_id"]),
            models.Index(fields=["team_id"]),
        ]


class Preferences(models.Model):
    id = models.BigAutoField(primary_key=True)
    org_id = models.BigIntegerField(default=0)
    user_id = models.BigIntegerField(default=0)
    team_id = models.BigIntegerField(null=True, default=0)
    version = models.IntegerField(default=0)
    home_dashboard_id = models.BigIntegerField(default=0)
    timezone = models.CharField(max_length=50, blank=True, default="")
    theme = models.CharField(max_length=20, blank=True, default="")
    week_start = models.CharField(max_length=10, null=True, default="")
    json_data = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "preferences"
        app_label = APP_LABEL
        managed = False
        indexes = [
            models.Index(fields=["org_id"]),
            models.Index(fields=["user_id"]),
        ]


class Permission(models.Model):
    id = models.BigAutoField(primary_key=True)
    role_id = models.BigIntegerField()
    action = models.CharField(max_length=190)
    scope = models.CharField(max_length=190)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "permission"
        app_label = APP_LABEL
        managed = False
        unique_together = (("role_id", "action", "scope"),)
        indexes = [models.Index(fields=["role_id"])]


class BuiltinRole(models.Model):
    id = models.BigAutoField(primary_key=True)
    role = models.CharField(max_length=190, db_index=True)
    role_id = models.BigIntegerField(db_index=True)
    org_id = models.BigIntegerField(default=0, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "builtin_role"
        app_label = APP_LABEL
        managed = False
        unique_together = (("org_id", "role_id", "role"),)


class Role(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=190, db_index=True)
    description = models.TextField(blank=True, default="")
    version = models.BigIntegerField(default=0)
    org_id = models.BigIntegerField(db_index=True)
    uid = models.CharField(max_length=40, blank=True, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    display_name = models.CharField(max_length=190, null=True, blank=True, default="")
    group_name = models.CharField(max_length=190, null=True, blank=True, default="")
    hidden = models.BooleanField(default=False)

    class Meta:
        db_table = "role"
        app_label = APP_LABEL
        managed = False
        unique_together = (("org_id", "name"),)


class Star(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_id = models.BigIntegerField()
    dashboard_id = models.BigIntegerField()

    class Meta:
        db_table = "star"
        app_label = APP_LABEL
        managed = False
