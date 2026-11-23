from flask import Blueprint, render_template

bp = Blueprint("coffre", __name__)


@bp.get("/coffre")
def index():
    return render_template("coffre.html")
