from django import forms


class StyleCoachForm(forms.Form):
    question=forms.CharField(
        max_length=800,
        widget=forms.Textarea(attrs={
            "rows":4,"placeholder":"Ask about your wardrobe… e.g. What should I buy next?",
            "class":"input"
        }),
    )
