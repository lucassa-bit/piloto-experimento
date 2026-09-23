# Lexical Context

- Conteúdo recomendado é um item de conteúdo associado a um evento noticioso elegível.
- News event é um acontecimento noticioso identificado a partir das fontes de notícias cadastradas.
- A área do usuário corresponde ao município associado ao seu perfil.

# Operational Context

- A relevância é determinada por uma pontuação que combina recência e importância atribuída ao evento.
- Apenas eventos noticiosos das últimas 24 horas são elegíveis para recomendação.
- O sistema retorna no máximo dez recomendações.
- As recomendações são ordenadas pela pontuação de relevância, da maior para a menor.
- O sistema informa que não existem recomendações locais disponíveis e não amplia automaticamente a região.

# Decisional Context

- Foi decidido utilizar a localização registrada no perfil e não exigir acesso à localização atual do dispositivo.

# Systemic Context

- A área do usuário é obtida do município registrado no serviço de perfil.
- Os eventos são obtidos do serviço de notícias utilizado pela plataforma.
