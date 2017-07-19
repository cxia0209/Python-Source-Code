a = 1

def f():
  a = 2
  def g():
    global a
    print a
    a += 2
  return g

g = f()
g()
print(a)
