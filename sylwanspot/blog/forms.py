from django import forms

from .models import Comment


class EmailPostForm(forms.Form):
    name = forms.CharField(max_length=25, label="nadawca")
    email = forms.EmailField(label="twój email")
    to = forms.EmailField(label="email odbiorcy")
    comments = forms.CharField(required=False, widget=forms.Textarea, label="treść")


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["name", "email", "body"]
        labels = {
            "name": "nickname",
            "email": "e-mail",
            "body": "treść komentarza",
        }


class SearchForm(forms.Form):
    query = forms.CharField(label="Szukana fraza:")