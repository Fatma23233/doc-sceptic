from doc_sceptic.corpus import split,sections
def test_split():assert len(split('x'*4000))>1
def test_sections():assert sections('# A\ntext','x')[0][0]=='A'
