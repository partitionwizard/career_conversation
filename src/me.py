from pypdf import PdfReader
class Me:
    def __init__(self):
        reader = PdfReader("src/me/Suraj-Linkedin.pdf")
        linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                linkedin += text
        reader = PdfReader("src/me/Suraj-Resume-Data-Engineer.pdf")
        resume = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                resume += text
        self.about = resume + linkedin
        self.name = "Suraj Bondugula"