from flask import Blueprint, render_template

bp = Blueprint("solidarite", __name__)


@bp.get("/solidarite")
def index():
    return render_template("solidarite.html")
