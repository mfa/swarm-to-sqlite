import datetime
from sqlite_utils.db import AlterError


def save_checkin(checkin, db):
    if "venue" in checkin:
        venue = checkin.pop("venue")
        categories = venue.pop("categories")
        venue.update(venue.pop("location"))
        venue.pop("labeledLatLngs", None)
        venue["latitude"] = venue.pop("lat")
        venue["longitude"] = venue.pop("lng")
        v = db["venues"].upsert(venue, pk="id", alter=True)
        for category in categories:
            cleanup_category(category)
            v.m2m("categories", category, pk="id")
        checkin["venue"] = venue["id"]
    else:
        checkin["venue"] = None
    checkin["createdAt"] = datetime.datetime.fromtimestamp(
        checkin["createdAt"]
    ).isoformat()
    checkin["source"] = db["sources"].lookup(checkin["source"])
    users_with = checkin.pop("with", None) or []
    users_likes = []
    for group in checkin["likes"]["groups"]:
        users_likes.extend(group["items"])
    del checkin["likes"]
    photos = checkin.pop("photos")["items"]
    if checkin.get("createdBy"):
        created_by_user = checkin.pop("createdBy")
        cleanup_user(created_by_user)
        db["users"].upsert(created_by_user, pk="id")
        checkin["createdBy"] = created_by_user["id"]
    # Actually save the checkin
    checkins_table = db["checkins"].upsert(
        checkin,
        pk="id",
        foreign_keys=(("venue", "venues", "id"), ("source", "sources", "id")),
        alter=True,
    )
    # Save m2m 'with' users and 'likes' users
    for user in users_with:
        cleanup_user(user)
        checkins_table.m2m("users", user, m2m_table="with", pk="id")
    for user in users_likes:
        cleanup_user(user)
        checkins_table.m2m("users", user, m2m_table="likes", pk="id")
    # Handle photos
    photos_table = db.table("photos", pk="id", foreign_keys=("user", "source"))
    for photo in photos:
        photo["createdAt"] = datetime.datetime.fromtimestamp(
            photo["createdAt"]
        ).isoformat()
        photo["source"] = db["sources"].lookup(photo["source"])
        user = photo.pop("user")
        cleanup_user(user)
        db["users"].upsert(user, pk="id")
        photo["user"] = user["id"]
        photos_table.upsert(photo)
    # Add checkin.createdBy => users.id foreign key last, provided the
    # users table exists
    if "users" in db.table_names() and "createdBy" in db["checkins"].columns_dict:
        try:
            db["checkins"].add_foreign_key("createdBy", "users", "id")
        except AlterError:
            pass


def cleanup_user(user):
    photo = user.pop("photo", None) or {}
    user["photo_prefix"] = photo.get("prefix")
    user["photo_suffix"] = photo.get("suffix")


def cleanup_category(category):
    category["icon_prefix"] = category["icon"]["prefix"]
    category["icon_suffix"] = category["icon"]["suffix"]
    del category["icon"]