import ast

from ply import yacc

from util import sqlerror
import lexer

DEBUG = False
tokens = lexer.tokens

class Statement(object):
    def __init__(self, fields, frm, where, groupby, orderby, limit):
        self.fields = fields
        self.frm = frm
        self.where = where
        self.groupby = groupby
        self.orderby = orderby
        self.limit = limit

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        s = "Statement(fields=%s, frm=%s, where=%s, groupby=%s, orderby=%s, limit=%s)"
        f = ast.dump(self.fields) if self.fields else "None"
        w = ast.dump(self.where) if self.where else "None"
        return s % (
                f,
                self.frm,
                w,
                self.groupby,
                self.orderby,
                self.limit,
        )

precedence = (
        ('left', 'OPERATOR'),
    )

def p_error(p):
    sqlerror(p)

def p_statement(p):
    'statement : select fields from where group order limit'
    p[0] = Statement(p[2], p[3], p[4], p[5], p[6], p[7])

def p_select(p):
    '''select :
              | SELECT'''

def p_fields(p):
    'fields : field fieldlist'
    if p[2] is not None:
        fields = p[1] + p[2]
    else:
        fields = p[1]
    p[0] = list_to_ast_dict(fields)

def p_field(p):
    '''field : STAR
             | IDENTIFIER
             | INTEGER
             | STRING
             | function
             | field AS IDENTIFIER'''
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        # foo AS bar
        # p[1] is already a 'field', which means that it's a 1-item list,
        # so we'll extract it below (p[1][0])
        p[0] = [(p[1][0], p[3])]

def p_fieldlist(p):
    '''fieldlist :
                 | COMMA field fieldlist'''
    if len(p) > 1:
        if p[3] != None:
            p[0] = p[2] + p[3]
        else:
            p[0] = p[2]

def p_function(p):
    'function : fname LPAREN field fieldlist RPAREN'
    if type(p[3][0]) == ast.Name:
        params = [ast.Name('__data__', ast.Load()), ast.Str(p[3][0].id)]
    else:
        params = [ast.Name('__data__', ast.Load()), p[3][0]]
    if p[4] is not None:
        for x in p[4]:
            if type(x) == ast.Name:
                params.append(ast.Str(x.id))
            else:
                params.append(x)
    p[0] = ast.Call(p[1], params, [], None, None)

def p_fname(p):
    'fname : IDENTIFIER'
    p[0] = p[1]

def p_from(p):
    '''from :
            | FROM IDENTIFIER'''

def p_where(p):
    '''where :
             | WHERE wherelist'''
    if len(p) > 1:
            p[0] = ast.Expression(p[2])

def p_wherelist(p):
    '''wherelist : 
                 | wherexpr
                 | wherexpr AND wherelist
                 | wherexpr OR wherelist'''
    if len(p) == 4:
            rval = [p[1], p[3]]
            p[0] = ast.BoolOp(p[2], rval)
    else:
        if len(p) > 1:
            #p[0] = p[1], p[2]
            p[0] = p[1]

def p_wherexpr(p):
    '''wherexpr : whereval OPERATOR whereval
                | whereval IN inlist
                | whereval BETWEEN whereval AND whereval
                | wherexpr_grouped'''
    if len(p) == 4:
        # field = value
        lval = p[1]
        rval = p[3]
        p[0] = ast.Compare(
                    left=lval,
                    ops=[p[2]],
                    comparators=[rval]
                )
    elif len(p) == 6:
        # between 1 and 10
        # this is analogous to:
        #  p[1] >= p[3] and p[1] <= p[5]
        p[0] = ast.BoolOp(ast.And(), [
                ast.Compare(
                    p[1],
                    [ast.GtE()],
                    [p[3]]
                ),
                ast.Compare(
                    p[1],
                    [ast.LtE()],
                    [p[5]]
                )
            ])
    else:
        # group
        p[0] = p[1]

def p_inlist(p):
    'inlist : LPAREN initem initemlist RPAREN'
    if p[3] is not None:
        p[0] = ast.Tuple([p[2]] + p[3], ast.Load())
    else:
        p[0] = ast.Tuple([p[2]], ast.Load())

def p_initemlist(p):
    '''initemlist : 
                  | COMMA initem initemlist'''
    if len(p) > 1:
        if p[3] != None:
            p[0] = [p[2]] + p[3]
        else:
            p[0] = [p[2]]

def p_initem(p):
    '''initem : STRING
              | INTEGER
              | IDENTIFIER'''
    p[0] = p[1]

def p_wherexpr_grouped(p):
    'wherexpr_grouped : LPAREN wherelist RPAREN'
    p[0] = p[2]

def p_whereval(p):
    '''whereval : IDENTIFIER
                | INTEGER
                | STRING'''
    p[0] = p[1]

def p_group(p):
    '''group :
             | GROUP BY IDENTIFIER identlist'''
    if len(p) > 1:
        if p[4] is None:
            fields = [p[3]]
        else:
            fields = [p[3]] + p[4]
        names = []
        for f in fields:
            names.append(f.id)
        p[0] = names

def p_order(p):
    '''order :
             | ORDER BY IDENTIFIER identlist direction'''
    if len(p) > 1:
        if p[4] is not None:
            fields = [p[3]] + p[4]
        else:
            fields = [p[3]]
        names = []
        for f in fields:
            names.append(f.id)
        p[0] = (names, p[5])

def p_direction(p):
    '''direction :
                 | ASC
                 | DESC'''
    try:
        p[0] = p[1]
    except IndexError:
        p[0] = 'asc' # default to 'asc'

def p_identlist(p):
    '''identlist :
                 | COMMA IDENTIFIER identlist'''
    if len(p) > 1:
        if p[3] != None:
            p[0] = [p[2]] + p[3]
        else:
            p[0] = [p[2]]

def p_limit(p):
    '''limit :
             | LIMIT INTEGER
             | LIMIT INTEGER COMMA INTEGER'''
    if len(p) > 1:
        if len(p) == 3:
            p[0] = (0, int(p[2].n))
        else:
            p[0] = (int(p[2].n), int(p[4].n))

_parser = None
_lexer = None
def init():
    global _parser, _lexer
    lexer.DEBUG = DEBUG
    _lexer = lexer.getlexer()
    _parser = yacc.yacc(debug=DEBUG)

def parse(sql):
    return _parser.parse(sql, lexer=_lexer, debug=DEBUG)

def __get_fieldname(f):
    if type(f) == ast.Name:
        return f.id
    elif type(f) == ast.Call:
        return "%s(%s)" % (f.func.id, ','.join([__get_fieldname(n) for n in f.args[1:]]))
    elif type(f) == ast.Str:
        return f.s
    elif type(f) == ast.Num:
        return str(f.n)
    else:
        return str(f)

def list_to_ast_dict(fields):
    _keys = []
    _values = []
    for f in fields:
        if type(f) == tuple:
            # this is an 'as' field (foo as bar)
            _keys.append(ast.Str(__get_fieldname(f[1])))
            _values.append(f[0])
        else:
            _keys.append(ast.Str(__get_fieldname(f)))
            _values.append(f)
    tpls = map(lambda x: ast.Tuple(list(x), ast.Load()), zip(_keys, _values))
    return ast.Expression(
            ast.Call(
                ast.Name('OrderedDict', ast.Load()),
                [ast.List(tpls, ast.Load())],
                [], None, None
            )
           )
