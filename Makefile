# THEME = --syntax-highlighting=my.theme
# RPATHS = --resource-path=Part-1:Part-2:Part-3:Part-4
# ENG = --pdf-engine=xelatex

%.pdf: %.md
	pandoc $< $(RPATHS) $(ENG) -o $@
