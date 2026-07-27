import pymysql

pymysql.install_as_MySQLdb()

# o pymysql se identifica como versao 1.4.6 por padrao, mas o Django exige
# que o driver diga que e 2.2.1 pra cima, entao a gente forca essa versao aqui
pymysql.version_info = (2, 2, 4, "final", 0)
pymysql.__version__ = "2.2.4"
