# Lexical Context

- Uma recycling facility é um local físico que recebe materiais recicláveis entregues por usuários.

# Operational Context

- O sistema aceita ZIP de 5 dígitos e ZIP+4.
- Uma instalação é considerada próxima quando está a até 25 km da região correspondente ao ZIP informado.
- A busca não é executada e o usuário recebe uma mensagem informando que o ZIP não pôde ser reconhecido.
- Apenas instalações com cadastro ativo e verificado podem aparecer nos resultados.
- Cada resultado apresenta nome, endereço, distância e tipos de materiais aceitos.
- As instalações são ordenadas pela distância, da mais próxima para a mais distante.
- O sistema informa que nenhuma instalação próxima foi encontrada e não amplia automaticamente o raio da busca.

# Decisional Context

- Foi decidido utilizar ZIP informado manualmente e não exigir acesso à localização do dispositivo.

# Systemic Context

- O ZIP é convertido em uma localização geográfica por um serviço de geocodificação utilizado pelo sistema.
- As instalações são obtidas do cadastro de instalações mantido pela plataforma.
